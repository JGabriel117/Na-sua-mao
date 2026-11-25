"""Servico de moderação: palavras proibidas, avaliações e denúncias (RN03, RN11)."""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.models.models import Avaliacao, Denuncia, Ferramenta, Reserva, Usuario
from src.repositories import (
    ferramenta_repository,
    moderacao_repository,
    reserva_repository,
    usuario_repository,
)
from src.services.usuario_service import ErroValidacao

PALAVRAS_PROIBIDAS = {
    "idiota", "imbecil", "burro", "otario", "otaria", "lixo", "merda", "porcaria",
    "desgracado", "desgracada", "vagabundo", "vagabunda", "ladrao", "ladra", "golpista",
    "estelionatario", "cretino", "babaca", "escroto", "canalha", "pilantra", "safado",
    "safada", "corrupto", "inutil", "retardado", "arrombado", "fdp", "puta", "bosta",
}

TAMANHO_MINIMO_COMENTARIO = 10

MOTIVOS_DENUNCIA = [
    "Anúncio falso ou enganoso",
    "Equipamento danificado ou diferente do anúncio",
    "Comportamento inadequado",
    "Cobrança indevida",
    "Golpe ou tentativa de fraude",
    "Outro motivo",
]

# Status possiveis de uma denuncia.
STATUS_DENUNCIA_ABERTA = "aberta"
STATUS_DENUNCIA_PROCEDENTE = "procedente"
STATUS_DENUNCIA_IMPROCEDENTE = "improcedente"
STATUS_DENUNCIA_ENCERRADA = "encerrada"
STATUS_DENUNCIA_VALIDOS = {
    STATUS_DENUNCIA_ABERTA,
    STATUS_DENUNCIA_PROCEDENTE,
    STATUS_DENUNCIA_IMPROCEDENTE,
    STATUS_DENUNCIA_ENCERRADA,
}


def validar_comentario(comentario: str) -> bool:
    """False quando o texto contem termo proibido ou e curto demais."""
    texto = (comentario or "").strip().lower()
    if len(texto) < TAMANHO_MINIMO_COMENTARIO:
        return False
    normalizado = texto.replace(".", "").replace(",", "").replace("-", " ")
    palavras = set(normalizado.split())
    for proibida in PALAVRAS_PROIBIDAS:
        if proibida in palavras or proibida in normalizado:
            return False
    return True


def avaliar(db: Session, reserva: Reserva, avaliador_id: int, nota: int, comentario: str) -> Avaliacao:
    if reserva.status_reserva not in ("concluida", "finalizada"):
        raise ErroValidacao("Só é possível avaliar reservas já concluídas.")
    if avaliador_id not in (reserva.id_locatario, reserva.id_locador):
        raise ErroValidacao("Você não participou desta locação.")
    if not validar_comentario(comentario):
        raise ErroValidacao(
            "Comentário recusado: use ao menos 10 caracteres e evite termos ofensivos."
        )

    ja_avaliou = moderacao_repository.avaliacao_do_avaliador_na_reserva(
        db, reserva.id_reserva, avaliador_id
    )
    if ja_avaliou:
        raise ErroValidacao("Você já avaliou esta locação.")

    avaliado = reserva.id_locador if avaliador_id == reserva.id_locatario else reserva.id_locatario
    avaliacao = Avaliacao(
        id_reserva=reserva.id_reserva,
        id_avaliador=avaliador_id,
        id_avaliado=avaliado,
        nota=max(1, min(5, int(nota or 5))),
        comentario=(comentario or "").strip(),
    )
    db.add(avaliacao)
    db.commit()
    db.refresh(avaliacao)
    return avaliacao


def denunciar(
    db: Session,
    denunciante_id: int,
    motivo: str,
    descricao: str,
    id_denunciado: int = None,
    id_ferramenta: int = None,
    id_avaliacao: int = None,
) -> Denuncia:
    motivo = (motivo or "").strip()
    descricao = (descricao or "").strip()

    if not motivo:
        raise ErroValidacao("Informe o motivo da denúncia.")
    if motivo not in MOTIVOS_DENUNCIA:
        raise ErroValidacao("Selecione um motivo válido para a denúncia.")
    if not validar_comentario(descricao):
        raise ErroValidacao(
            "Descrição recusada: conte o ocorrido com ao menos 10 caracteres e sem termos ofensivos."
        )

    avaliacao = None
    if id_avaliacao:
        avaliacao = moderacao_repository.obter_avaliacao(db, id_avaliacao)
        if not avaliacao:
            raise ErroValidacao("Avaliação não encontrada para a denúncia.")
        if avaliacao.id_avaliador == denunciante_id:
            raise ErroValidacao("Você não pode denunciar a sua própria avaliação.")
        # A denúncia de avaliação aponta sempre para o autor do comentário.
        id_denunciado = avaliacao.id_avaliador
        reserva = reserva_repository.obter(db, avaliacao.id_reserva)
        if reserva:
            id_ferramenta = reserva.id_ferramenta

    ferramenta = None
    if id_ferramenta:
        ferramenta = ferramenta_repository.obter(db, id_ferramenta)
        if not ferramenta:
            raise ErroValidacao("Anúncio não encontrado para a denúncia.")
        if ferramenta.id_locador == denunciante_id and not id_avaliacao:
            raise ErroValidacao("Você não pode denunciar o seu próprio anúncio.")
        id_denunciado = id_denunciado or ferramenta.id_locador

    if not id_denunciado and not id_ferramenta and not id_avaliacao:
        raise ErroValidacao("Selecione o anúncio, a avaliação ou o usuário que deseja denunciar.")
    if id_denunciado == denunciante_id:
        raise ErroValidacao("Você não pode denunciar a si mesmo.")

    if id_denunciado:
        alvo = usuario_repository.buscar_por_id(db, id_denunciado)
        if not alvo:
            raise ErroValidacao("Usuário denunciado não encontrado.")

    if moderacao_repository.denuncia_aberta_duplicada(
        db, denunciante_id, id_ferramenta, id_denunciado, id_avaliacao
    ):
        raise ErroValidacao("Você já enviou uma denúncia com este alvo e ela está em análise.")

    denuncia = Denuncia(
        id_denunciante=denunciante_id,
        id_denunciado=id_denunciado,
        id_ferramenta=id_ferramenta,
        id_avaliacao=id_avaliacao,
        motivo=motivo,
        descricao=descricao,
        status_denuncia=STATUS_DENUNCIA_ABERTA,
    )
    db.add(denuncia)
    db.commit()
    db.refresh(denuncia)
    return denuncia


def listar_denuncias(db: Session, limite: int = 50, status: Optional[str] = None):
    return moderacao_repository.listar_denuncias(db, limite=limite, status=status)


def contar_denuncias_abertas(db: Session) -> int:
    return moderacao_repository.contar_denuncias_abertas(db)


def _obter_denuncia(db: Session, id_denuncia: int) -> Denuncia:
    denuncia = moderacao_repository.obter_denuncia(db, id_denuncia)
    if not denuncia:
        raise ErroValidacao("Denúncia não encontrada.")
    return denuncia


def encerrar_denuncia(db: Session, id_denuncia: int, status: str = STATUS_DENUNCIA_ENCERRADA) -> Denuncia:
    """Mantido para compatibilidade: encerra a denuncia sem julgar o mérito."""
    denuncia = _obter_denuncia(db, id_denuncia)
    if status not in STATUS_DENUNCIA_VALIDOS:
        raise ErroValidacao("Status de denúncia inválido.")
    denuncia.status_denuncia = status
    db.commit()
    db.refresh(denuncia)
    return denuncia


def resolver_denuncia(db: Session, id_denuncia: int, status: str) -> Denuncia:
    """Aprova (procedente) ou rejeita (improcedente) uma denúncia (RN11)."""
    if status not in (STATUS_DENUNCIA_PROCEDENTE, STATUS_DENUNCIA_IMPROCEDENTE):
        raise ErroValidacao("Escolha aprovar ou rejeitar a denúncia.")
    denuncia = _obter_denuncia(db, id_denuncia)
    if denuncia.status_denuncia != STATUS_DENUNCIA_ABERTA:
        raise ErroValidacao("Esta denúncia já foi analisada.")
    denuncia.status_denuncia = status
    db.commit()
    db.refresh(denuncia)
    return denuncia


def suspender_ferramenta(db: Session, id_ferramenta: int) -> Ferramenta:
    ferramenta = ferramenta_repository.obter(db, id_ferramenta)
    if not ferramenta:
        raise ErroValidacao("Anúncio não encontrado.")
    if ferramenta.excluida:
        raise ErroValidacao("Este anúncio já foi excluído pelo locador.")
    ferramenta.status_ferramenta = "suspensa"
    db.commit()
    db.refresh(ferramenta)
    return ferramenta


def remover_anuncio_por_denuncia(db: Session, id_ferramenta: int) -> dict:
    """Remove o anúncio denunciado e todos os dados operacionais vinculados.

    A denúncia é mantida para histórico, mas perde o vínculo com o anúncio e
    com a avaliação removida. A operação é transacional.
    """
    ferramenta = ferramenta_repository.obter(db, id_ferramenta)
    if not ferramenta:
        raise ErroValidacao("Anúncio não encontrado ou já removido.")
    titulo = ferramenta.titulo
    try:
        contagens = moderacao_repository.purgar_dados_operacionais(db, id_ferramenta)
        moderacao_repository.remover_ferramenta(db, ferramenta)
    except Exception as exc:  # noqa: BLE001 - devolve erro de negocio ao controller
        db.rollback()
        raise ErroValidacao("Não foi possível remover o anúncio. Tente novamente.") from exc
    db.expire_all()
    return {"id_ferramenta": id_ferramenta, "titulo": titulo, **contagens}


def reativar_ferramenta(db: Session, id_ferramenta: int) -> Ferramenta:
    ferramenta = ferramenta_repository.obter(db, id_ferramenta)
    if not ferramenta:
        raise ErroValidacao("Anúncio não encontrado.")
    if ferramenta.excluida:
        raise ErroValidacao("Anúncios excluídos pelo locador não podem ser reativados.")
    ferramenta.status_ferramenta = "disponivel"
    db.commit()
    db.refresh(ferramenta)
    return ferramenta


def suspender_usuario(db: Session, id_usuario: int) -> Usuario:
    usuario = usuario_repository.buscar_por_id(db, id_usuario)
    if not usuario:
        raise ErroValidacao("Usuário não encontrado.")
    if usuario.is_admin:
        raise ErroValidacao("Contas administrativas não podem ser suspensas por esta tela.")
    usuario.status_conta = "suspensa"
    db.commit()
    db.refresh(usuario)
    return usuario


def reativar_usuario(db: Session, id_usuario: int) -> Usuario:
    usuario = usuario_repository.buscar_por_id(db, id_usuario)
    if not usuario:
        raise ErroValidacao("Usuário não encontrado.")
    usuario.status_conta = "ativa"
    db.commit()
    db.refresh(usuario)
    return usuario


def registrar_aviso_moderacao(db: Session, id_denuncia: int, observacao: str) -> Denuncia:
    """Guarda a conclusao da analise no proprio registro da denuncia."""
    denuncia = _obter_denuncia(db, id_denuncia)
    nota = (observacao or "").strip()
    if nota:
        base = (denuncia.descricao or "").strip()
        denuncia.descricao = f"{base}\n\n[Moderação {datetime.utcnow():%d/%m/%Y %H:%M}] {nota}"[:2000]
    db.commit()
    db.refresh(denuncia)
    return denuncia


def contexto_denuncia(
    db: Session,
    denunciante_id: int,
    ferramenta: int = 0,
    usuario_id: int = 0,
    avaliacao: int = 0,
) -> dict:
    """Monta os dados do alvo da denúncia para a tela /denunciar."""
    contexto = {
        "id_ferramenta": 0,
        "id_denunciado": 0,
        "id_avaliacao": 0,
        "alvo_tipo": "",
        "alvo_titulo": "",
        "alvo_detalhe": "",
        "voltar": "/",
    }

    if avaliacao:
        alvo = moderacao_repository.obter_avaliacao(db, avaliacao)
        if not alvo:
            raise ErroValidacao("Avaliação não encontrada.")
        if alvo.id_avaliador == denunciante_id:
            raise ErroValidacao("Você não pode denunciar a sua própria avaliação.")
        reserva = reserva_repository.obter(db, alvo.id_reserva)
        ferramenta_alvo = ferramenta_repository.obter(db, reserva.id_ferramenta) if reserva else None
        contexto.update(
            id_avaliacao=alvo.id_avaliacao,
            id_denunciado=alvo.id_avaliador,
            id_ferramenta=ferramenta_alvo.id_ferramenta if ferramenta_alvo else 0,
            alvo_tipo="Avaliação",
            alvo_titulo=f"Avaliação #{alvo.id_avaliacao} · nota {alvo.nota}/5",
            alvo_detalhe=(
                (alvo.comentario or "Sem comentário.")
                + f" — autor: {alvo.avaliador.nome if alvo.avaliador else 'Vizinho'}"
            ),
            voltar=f"/ferramentas/{ferramenta_alvo.id_ferramenta}#avaliacoes" if ferramenta_alvo else "/",
        )
        return contexto

    if ferramenta:
        alvo = ferramenta_repository.obter(db, ferramenta)
        if not alvo:
            raise ErroValidacao("Anúncio não encontrado.")
        if alvo.id_locador == denunciante_id:
            raise ErroValidacao("Você não pode denunciar o seu próprio anúncio.")
        contexto.update(
            id_ferramenta=alvo.id_ferramenta,
            id_denunciado=alvo.id_locador,
            alvo_tipo="Anúncio",
            alvo_titulo=alvo.titulo,
            alvo_detalhe=f"Anunciado por {alvo.locador.nome}",
            voltar=f"/ferramentas/{ferramenta}",
        )
        return contexto

    if usuario_id:
        alvo = usuario_repository.buscar_por_id(db, usuario_id)
        if not alvo:
            raise ErroValidacao("Usuário não encontrado.")
        if alvo.id_usuario == denunciante_id:
            raise ErroValidacao("Você não pode denunciar a si mesmo.")
        contexto.update(
            id_denunciado=alvo.id_usuario,
            alvo_tipo="Usuário",
            alvo_titulo=alvo.nome,
            alvo_detalhe=f"Conta criada em {alvo.created_at:%d/%m/%Y}",
        )
        return contexto

    raise ErroValidacao("Selecione um anúncio, avaliação ou usuário para denunciar.")


def dados_moderacao_usuario(db: Session, id_usuario: int) -> dict:
    """Dados completos de um usuário para a tela administrativa de perfil."""
    usuario = usuario_repository.buscar_por_id(db, id_usuario)
    if not usuario:
        raise ErroValidacao("Usuário não encontrado.")
    return {
        "alvo": usuario,
        "anuncios": ferramenta_repository.listar_do_locador(db, id_usuario, incluir_excluidas=True),
        "reservas": reserva_repository.listar_do_usuario(db, id_usuario),
        "avaliacoes": ferramenta_repository.avaliacoes_recebidas(db, id_usuario),
        "denuncias_contra": moderacao_repository.listar_denuncias_contra(db, id_usuario),
        "denuncias_feitas": moderacao_repository.listar_denuncias_feitas(db, id_usuario),
    }


def estatisticas_painel(db: Session) -> dict:
    return {
        "total_usuarios": usuario_repository.contar(db, somente_admin=False),
        "total_admins": usuario_repository.contar(db, somente_admin=True),
        "total_ferramentas": ferramenta_repository.contar_publicas(db),
        "total_denuncias_abertas": moderacao_repository.contar_denuncias_abertas(db),
    }
