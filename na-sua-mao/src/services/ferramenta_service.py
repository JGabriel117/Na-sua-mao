"""Servico de ferramentas: publicação, filtros do catálogo e cálculo de distância."""

import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Sequence

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.integrations import storage_service
from src.models.models import Categoria, Ferramenta, Usuario
from src.repositories import ferramenta_repository
from src.services.usuario_service import ErroValidacao

ESTADOS_CONSERVACAO = ["Novo", "Usado - Excelente", "Usado - Bom", "Usado - Regular"]
VOLTAGENS = ["110V", "220V", "Bivolt", "Bateria", "Manual"]
STATUS_RESERVA_ATIVA = ("aprovada", "em_uso")
# Reservas que impedem a exclusao do anuncio (historico ainda em andamento).
STATUS_BLOQUEIA_EXCLUSAO = ("pendente", "aprovada", "em_uso")
STATUS_OCULTOS_CATALOGO = ("excluida", "suspensa")

# Raio aplicado por padrão quando o usuário já tem localização definida.
RAIO_PADRAO_KM = 10.0


def listar_categorias(db: Session) -> Sequence[Categoria]:
    return ferramenta_repository.listar_categorias(db)


def calcular_distancia(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância aproximada em quilometros (formula de Haversine)."""
    raio_terra = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return float(2 * raio_terra * math.asin(math.sqrt(a)))


def _condicoes_termo(termo: str):
    """Traduz a busca digitada em condicoes SQL.

    Virgula/ponto e virgula separam alternativas (OR); espacos dentro de cada
    grupo sao refinamentos (AND). Ex.:
        "furadeira, escada"      -> furadeira OU escada
        "furadeira de impacto"   -> furadeira E de E impacto
    """
    grupos = [g.strip() for g in re.split(r"[,;]", termo or "") if g.strip()]
    condicoes = []
    for grupo in grupos:
        tokens = [t for t in re.split(r"\s+", grupo) if len(t) >= 2]
        if not tokens:
            tokens = [grupo]
        partes = [
            or_(
                Ferramenta.titulo.ilike(f"%{t}%"),
                Ferramenta.descricao.ilike(f"%{t}%"),
                Categoria.nome.ilike(f"%{t}%"),
            )
            for t in tokens
        ]
        condicoes.append(and_(*partes))
    return condicoes


def buscar_catalogo(
    db: Session,
    termo: str = "",
    id_categoria: Optional[int] = None,
    estado: str = "",
    voltagem: str = "",
    usuario: Optional[Usuario] = None,
    distancia_maxima: Optional[float] = None,
):
    consulta = ferramenta_repository.consulta_catalogo(db)

    condicoes = _condicoes_termo(termo)
    if condicoes:
        consulta = consulta.filter(or_(*condicoes))

    if id_categoria:
        consulta = consulta.filter(Ferramenta.id_categoria == id_categoria)
    if estado:
        consulta = consulta.filter(Ferramenta.estado_conservacao == estado)
    if voltagem:
        consulta = consulta.filter(Ferramenta.voltagem == voltagem)

    ferramentas = consulta.order_by(Ferramenta.created_at.desc()).all()

    if usuario and usuario.latitude is not None and usuario.longitude is not None:
        for ferramenta in ferramentas:
            locador = ferramenta.locador
            if locador and locador.latitude is not None and locador.longitude is not None:
                ferramenta.distancia_km = round(
                    calcular_distancia(usuario.latitude, usuario.longitude, locador.latitude, locador.longitude), 1
                )
            else:
                ferramenta.distancia_km = None
        if distancia_maxima:
            ferramentas = [
                f for f in ferramentas if f.distancia_km is not None and f.distancia_km <= distancia_maxima
            ]

    return ferramentas


def obter(db: Session, id_ferramenta: int) -> Optional[Ferramenta]:
    return ferramenta_repository.obter(db, id_ferramenta)


def obter_publica(db: Session, id_ferramenta: int) -> Optional[Ferramenta]:
    """Anuncio visivel ao publico: ignora excluidos e suspensos."""
    ferramenta = obter(db, id_ferramenta)
    if not ferramenta or not ferramenta.publica:
        return None
    return ferramenta


def _converter_preco(valor: str) -> Decimal:
    texto = (valor or "").replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        preco = Decimal(texto)
    except (InvalidOperation, AttributeError) as exc:
        raise ErroValidacao("Informe um valor de diária válido.") from exc
    if preco <= 0:
        raise ErroValidacao("O valor da diária deve ser maior que zero.")
    return preco.quantize(Decimal("0.01"))


def criar_ferramenta(
    db: Session,
    locador: Usuario,
    titulo: str,
    descricao: str,
    id_categoria: int,
    estado_conservacao: str,
    voltagem: str,
    preco_diaria: str,
    arquivos: Sequence = (),
) -> Ferramenta:
    titulo = (titulo or "").strip()
    if len(titulo) < 5:
        raise ErroValidacao("O título do anúncio deve ter pelo menos 5 caracteres.")
    if not id_categoria:
        raise ErroValidacao("Selecione uma categoria.")
    if not estado_conservacao:
        raise ErroValidacao("Selecione o estado de conservação.")
    if not (descricao or "").strip():
        raise ErroValidacao("Descreva a ferramenta para os vizinhos.")

    preco = _converter_preco(preco_diaria)

    fotos = []
    for arquivo in (arquivos or [])[:5]:
        if arquivo is None or not getattr(arquivo, "filename", ""):
            continue
        try:
            fotos.append(storage_service.salvar_imagem(arquivo))
        except ValueError as exc:
            raise ErroValidacao(str(exc)) from exc

    if not fotos:
        raise ErroValidacao("Envie pelo menos uma foto da ferramenta (PNG, JPG, JPEG ou WEBP).")

    ferramenta = Ferramenta(
        id_locador=locador.id_usuario,
        id_categoria=int(id_categoria),
        titulo=titulo,
        descricao=descricao.strip(),
        voltagem=voltagem or None,
        estado_conservacao=estado_conservacao,
        preco_diaria=preco,
        status_ferramenta="disponivel",
        foto1=fotos[0],
        foto2=fotos[1] if len(fotos) > 1 else None,
        foto3=fotos[2] if len(fotos) > 2 else None,
        foto4=fotos[3] if len(fotos) > 3 else None,
        foto5=fotos[4] if len(fotos) > 4 else None,
    )
    db.add(ferramenta)
    db.commit()
    db.refresh(ferramenta)
    return ferramenta


def listar_do_locador(db: Session, usuario: Usuario):
    return ferramenta_repository.listar_do_locador(db, usuario.id_usuario)


def alternar_disponibilidade(db: Session, ferramenta: Ferramenta, ativo: bool) -> Ferramenta:
    if not ferramenta.publica:
        raise ErroValidacao("Este anúncio não está mais ativo e não pode ser alterado.")
    em_uso = ferramenta_repository.primeira_reserva_com_status(
        db, ferramenta.id_ferramenta, STATUS_RESERVA_ATIVA
    )
    if em_uso:
        raise ErroValidacao("Não é possível alterar: existe reserva ativa para esta ferramenta.")
    ferramenta.status_ferramenta = "disponivel" if ativo else "indisponivel"
    db.commit()
    db.refresh(ferramenta)
    return ferramenta


def excluir_ferramenta(db: Session, ferramenta: Ferramenta, usuario: Usuario) -> Ferramenta:
    """Soft delete do anuncio (RN09).

    O registro permanece no banco para preservar contratos, reservas e o
    historico de auditoria; apenas sai do catalogo e do painel do locador.
    """
    if ferramenta.id_locador != usuario.id_usuario:
        raise ErroValidacao("Você não tem permissão para excluir este anúncio.")
    if ferramenta.excluida:
        raise ErroValidacao("Este anúncio já foi excluído.")

    reserva_ativa = ferramenta_repository.primeira_reserva_com_status(
        db, ferramenta.id_ferramenta, STATUS_BLOQUEIA_EXCLUSAO
    )
    if reserva_ativa:
        raise ErroValidacao(
            "Este anúncio possui reserva ativa e não pode ser excluído. "
            "Conclua ou cancele a locação antes de removê-lo."
        )

    ferramenta.status_ferramenta = "excluida"
    ferramenta.excluida_em = datetime.utcnow()
    db.commit()
    db.refresh(ferramenta)
    return ferramenta


def media_avaliacoes(db: Session, id_usuario: int):
    registros = ferramenta_repository.avaliacoes_recebidas(db, id_usuario)
    if not registros:
        return None, 0
    return round(sum(r.nota for r in registros) / len(registros), 1), len(registros)


def avaliacoes_recebidas(db: Session, id_usuario: int):
    """Avaliacoes recebidas por um usuario, da mais recente para a mais antiga."""
    return ferramenta_repository.avaliacoes_recebidas(db, id_usuario)


def avaliacoes_da_ferramenta(db: Session, id_ferramenta: int):
    """Avaliacoes ligadas a reservas de um anuncio especifico."""
    return ferramenta_repository.avaliacoes_da_ferramenta(db, id_ferramenta)
