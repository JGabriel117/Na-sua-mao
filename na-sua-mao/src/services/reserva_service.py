"""Servico de reservas: conflito de agenda, termo de responsabilidade e cálculos."""

import hashlib
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.models.models import Contrato, Devolucao, Ferramenta, Reserva, Retirada, Usuario
from src.repositories import reserva_repository
from src.services.usuario_service import ErroValidacao

STATUS_ATIVOS = ("aprovada", "em_uso")
STATUS_CHAT = reserva_repository.STATUS_CHAT
PERCENTUAL_ATRASO = Decimal("0.5")


def _parse_data(valor: str, campo: str) -> date:
    try:
        return datetime.strptime((valor or "").strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ErroValidacao(f"Informe uma data valida para {campo}.") from exc


def calcular_total(preco_diaria, inicio: date, fim: date) -> Decimal:
    dias = (fim - inicio).days or 1
    return (Decimal(str(preco_diaria)) * dias).quantize(Decimal("0.01"))


def verificar_conflito(db: Session, id_ferramenta: int, inicio: date, fim: date) -> bool:
    """RN02: existem reservas ativas sobrepostas ao período solicitado."""
    return reserva_repository.existe_conflito(db, id_ferramenta, inicio, fim)


def gerar_conteudo_contrato(ferramenta: Ferramenta, locador: Usuario, locatario: Usuario, inicio: date, fim: date, total: Decimal) -> str:
    dias = (fim - inicio).days or 1
    return (
        "TERMO DE RESPONSABILIDADE E ISENÇÃO DE SEGURANÇA\n"
        "CONTRATO DE LOCAÇÃO DE FERRAMENTA\n\n"
        f"LOCADOR: {locador.nome} (CPF {locador.cpf})\n"
        f"LOCATÁRIO: {locatario.nome} (CPF {locatario.cpf})\n"
        f"OBJETO: {ferramenta.titulo} — estado de conservação "
        f"{ferramenta.estado_conservacao or 'não informado'}\n"
        f"PERÍODO: de {inicio.isoformat()} a {fim.isoformat()} ({dias} diária(s))\n"
        f"VALOR TOTAL: R$ {total}\n\n"
        "1. RESPONSABILIDADE PELO USO\n"
        "O LOCATÁRIO declara ter recebido o equipamento em perfeito funcionamento, "
        "foi orientado sobre a operação e assume integral responsabilidade pela "
        "utilização, guarda e conservação do bem durante todo o período da locação.\n\n"
        "2. SEGURANÇA E EPIs\n"
        "O LOCATÁRIO compromete-se a utilizar o equipamento conforme as instruções do "
        "fabricante, em local adequado e com os equipamentos de proteção individual "
        "necessários. Atividades de risco (elétrica, altura, corte, impacto) exigem "
        "capacitação prévia do usuário.\n\n"
        "3. DANOS, EXTRAVIO E ATRASO\n"
        "O LOCATÁRIO responde por danos, extravios e pela devolução fora do prazo, "
        "respondendo pelos valores apurados entre as partes. A taxa informativa de "
        "atraso corresponde a 50% da diária por dia excedente.\n\n"
        "4. ISENÇÃO DA PLATAFORMA\n"
        "A plataforma Na Sua Mão atua exclusivamente como intermediadora de contato "
        "entre vizinhos, não sendo proprietária, fabricante, transportadora ou seguradora "
        "do bem. A plataforma não se responsabiliza por acidentes, danos materiais, "
        "danos pessoais ou prejuízos decorrentes do uso do equipamento, que são de "
        "responsabilidade exclusiva do locador e do locatário.\n\n"
        "5. VERACIDADE DAS INFORMAÇÕES\n"
        "O LOCADOR declara ser legítimo proprietário do bem e que as informações do "
        "anúncio são verdadeiras. O LOCATÁRIO declara ter lido o anúncio e conferido o "
        "equipamento no momento da retirada.\n\n"
        "6. PRIVACIDADE E DADOS PESSOAIS\n"
        "Os dados pessoais são tratados conforme a LGPD e utilizados apenas para a "
        "operação da locação, segurança e histórico de reputação.\n\n"
        "Este termo é aceito eletronicamente, possui rastreabilidade por hash SHA-256 e "
        "fica vinculado à reserva e ao registro de auditoria da plataforma."
    )


def solicitar_reserva(
    db: Session,
    locatario: Usuario,
    ferramenta: Ferramenta,
    data_inicio: str,
    data_fim: str,
    aceite_termo: bool,
) -> Reserva:
    if ferramenta is None:
        raise ErroValidacao("Ferramenta não encontrada.")

    # RN04 - restricao de auto-aluguel
    if ferramenta.id_locador == locatario.id_usuario:
        raise ErroValidacao("Você e o proprietário desta ferramenta.")

    # RN06 - administradores nao realizam reservas
    if locatario.is_admin:
        raise ErroValidacao("Contas administrativas não realizam reservas.")

    # RN07 - aceite obrigatorio do termo de responsabilidade
    if not aceite_termo:
        raise ErroValidacao("É obrigatório aceitar o Termo de Responsabilidade e Isenção de Segurança.")

    if ferramenta.status_ferramenta != "disponivel":
        raise ErroValidacao("Esta ferramenta não está disponível para locação no momento.")

    inicio = _parse_data(data_inicio, "retirada")
    fim = _parse_data(data_fim, "devolucao")

    if inicio < date.today():
        raise ErroValidacao("A data de retirada não pode estar no passado.")
    if fim < inicio:
        raise ErroValidacao("A data de devolução deve ser igual ou posterior à retirada.")

    if verificar_conflito(db, ferramenta.id_ferramenta, inicio, fim):
        # Privacidade (RN10): nao revelamos quais datas estao ocupadas.
        raise ErroValidacao(
            "As datas escolhidas não estão disponíveis para este anúncio. "
            "Por favor, selecione outro período."
        )

    total = calcular_total(ferramenta.preco_diaria, inicio, fim)

    reserva = Reserva(
        id_locatario=locatario.id_usuario,
        id_locador=ferramenta.id_locador,
        id_ferramenta=ferramenta.id_ferramenta,
        data_prevista_inicio=inicio,
        data_prevista_fim=fim,
        valor_total_calculado=total,
        status_reserva="pendente",
    )
    db.add(reserva)
    db.flush()

    conteudo = gerar_conteudo_contrato(ferramenta, ferramenta.locador, locatario, inicio, fim, total)
    contrato = Contrato(
        id_reserva=reserva.id_reserva,
        conteudo=conteudo,
        hash_seguranca=hashlib.sha256(conteudo.encode("utf-8")).hexdigest(),
        aceite_locatario=True,
        aceite_locador=False,
    )
    db.add(contrato)
    db.commit()
    db.refresh(reserva)
    return reserva


def obter(db: Session, id_reserva: int) -> Reserva:
    reserva = reserva_repository.obter(db, id_reserva)
    if not reserva:
        raise ErroValidacao("Reserva não encontrada.")
    return reserva


def _autorizar(reserva: Reserva, usuario: Usuario, permitir_admin: bool = False) -> None:
    if permitir_admin and usuario.is_admin:
        return
    if usuario.id_usuario not in (reserva.id_locador, reserva.id_locatario):
        raise ErroValidacao("Você não tem permissão sobre esta reserva.")


def aprovar(db: Session, reserva: Reserva, usuario: Usuario) -> Reserva:
    if usuario.id_usuario != reserva.id_locador and not usuario.is_admin:
        raise ErroValidacao("Somente o locador pode aprovar esta solicitação.")
    if reserva.status_reserva != "pendente":
        raise ErroValidacao("Somente reservas pendentes podem ser aprovadas.")
    if reserva.ferramenta is None:
        raise ErroValidacao("O anúncio desta reserva não existe mais.")
    if reserva.ferramenta.status_ferramenta != "disponivel":
        raise ErroValidacao(
            "Este anúncio está suspenso ou indisponível. A reserva não pode ser aprovada."
        )
    if verificar_conflito(db, reserva.id_ferramenta, reserva.data_prevista_inicio, reserva.data_prevista_fim):
        raise ErroValidacao("Conflito de agenda: já existe reserva aprovada nesse período.")

    reserva.status_reserva = "aprovada"
    if reserva.contrato:
        reserva.contrato.aceite_locador = True
    db.commit()
    db.refresh(reserva)
    return reserva


def recusar(db: Session, reserva: Reserva, usuario: Usuario) -> Reserva:
    if usuario.id_usuario != reserva.id_locador and not usuario.is_admin:
        raise ErroValidacao("Somente o locador pode recusar esta solicitação.")
    if reserva.status_reserva != "pendente":
        raise ErroValidacao("Somente reservas pendentes podem ser recusadas.")
    reserva.status_reserva = "recusada"
    db.commit()
    db.refresh(reserva)
    return reserva


def cancelar(db: Session, reserva: Reserva, usuario: Usuario) -> Reserva:
    _autorizar(reserva, usuario, permitir_admin=True)
    if reserva.status_reserva in ("concluida", "cancelada", "recusada"):
        raise ErroValidacao("Esta reserva não pode mais ser cancelada.")
    reserva.status_reserva = "cancelada"
    db.commit()
    db.refresh(reserva)
    return reserva


def registrar_retirada(db: Session, reserva: Reserva, usuario: Usuario, observacao: str = "") -> Reserva:
    if usuario.id_usuario not in (reserva.id_locador, reserva.id_locatario):
        raise ErroValidacao("Você não participa desta reserva.")
    if reserva.status_reserva != "aprovada":
        raise ErroValidacao("Somente reservas aprovadas podem ser retiradas.")

    reserva.status_reserva = "em_uso"
    db.add(Retirada(id_reserva=reserva.id_reserva, confirmado_por=usuario.id_usuario, observacao=observacao or None))
    db.commit()
    db.refresh(reserva)
    return reserva


def calcular_taxa_atraso(preco_diaria, dias_atraso: int) -> Decimal:
    """RN05: taxa informativa proporcional aos dias excedentes (50% da diária por dia)."""
    dias = max(0, int(dias_atraso))
    return (Decimal(str(preco_diaria)) * PERCENTUAL_ATRASO * dias).quantize(Decimal("0.01"))


def registrar_devolucao(db: Session, reserva: Reserva, usuario: Usuario, estado: str = "", observacao: str = "") -> Reserva:
    if usuario.id_usuario not in (reserva.id_locador, reserva.id_locatario):
        raise ErroValidacao("Você não participa desta reserva.")
    if reserva.status_reserva not in ("aprovada", "em_uso"):
        raise ErroValidacao("Somente reservas ativas podem ser devolvidas.")

    hoje = date.today()
    atraso = max(0, (hoje - reserva.data_prevista_fim).days)
    taxa = calcular_taxa_atraso(reserva.ferramenta.preco_diaria, atraso)

    reserva.status_reserva = "concluida"
    db.add(
        Devolucao(
            id_reserva=reserva.id_reserva,
            estado_equipamento=estado or None,
            taxa_atraso=taxa,
            observacao=observacao or None,
        )
    )
    reserva.ferramenta.status_ferramenta = "disponivel"
    db.commit()
    db.refresh(reserva)
    return reserva


def listar_do_usuario(db: Session, usuario: Usuario):
    """Reservas em que o usuário e locatario ou locador."""
    return reserva_repository.listar_do_usuario(db, usuario.id_usuario)


def resumo_financeiro(db: Session, usuario: Usuario) -> dict:
    reservas = listar_do_usuario(db, usuario)
    saldo = sum(
        (Decimal(str(r.valor_total_calculado)) for r in reservas if r.id_locador == usuario.id_usuario and r.status_reserva == "concluida"),
        Decimal("0"),
    )
    a_receber = sum(
        (Decimal(str(r.valor_total_calculado)) for r in reservas if r.id_locador == usuario.id_usuario and r.status_reserva in STATUS_ATIVOS + ("pendente",)),
        Decimal("0"),
    )
    return {"saldo": saldo.quantize(Decimal("0.01")), "a_receber": a_receber.quantize(Decimal("0.01"))}


def conversas(db: Session, usuario: Usuario):
    """Apenas reservas aprovadas (ou já concluídas) liberam o chat."""
    return reserva_repository.listar_para_chat(db, usuario.id_usuario)


def pode_conversar(reserva: Reserva) -> bool:
    return reserva.status_reserva in STATUS_CHAT


def enviar_mensagem(db: Session, reserva: Reserva, usuario: Usuario, conteudo: str):
    _autorizar(reserva, usuario)
    if not pode_conversar(reserva):
        raise ErroValidacao("O chat é liberado depois que o locador aprovar a reserva.")
    texto = (conteudo or "").strip()
    if not texto:
        raise ErroValidacao("Escreva uma mensagem antes de enviar.")
    return reserva_repository.criar_mensagem(db, reserva.id_reserva, usuario.id_usuario, texto[:1000])
