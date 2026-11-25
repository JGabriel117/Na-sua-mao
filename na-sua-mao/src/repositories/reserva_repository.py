"""Consultas de reservas e mensagens."""

from datetime import date
from typing import Optional, Sequence

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.models.models import Mensagem, Reserva

STATUS_ATIVOS = ("aprovada", "em_uso")
STATUS_CHAT = ("aprovada", "em_uso", "concluida")


def obter(db: Session, id_reserva: int) -> Optional[Reserva]:
    return db.query(Reserva).filter(Reserva.id_reserva == id_reserva).first()


def listar_do_usuario(db: Session, id_usuario: int) -> Sequence[Reserva]:
    return (
        db.query(Reserva)
        .filter(or_(Reserva.id_locatario == id_usuario, Reserva.id_locador == id_usuario))
        .order_by(Reserva.created_at.desc())
        .all()
    )


def listar_para_chat(db: Session, id_usuario: int) -> Sequence[Reserva]:
    return (
        db.query(Reserva)
        .filter(
            or_(Reserva.id_locatario == id_usuario, Reserva.id_locador == id_usuario),
            Reserva.status_reserva.in_(STATUS_CHAT),
        )
        .order_by(Reserva.created_at.desc())
        .all()
    )


def existe_conflito(db: Session, id_ferramenta: int, inicio: date, fim: date) -> bool:
    return (
        db.query(Reserva.id_reserva)
        .filter(
            Reserva.id_ferramenta == id_ferramenta,
            Reserva.status_reserva.in_(STATUS_ATIVOS),
            and_(Reserva.data_prevista_inicio <= fim, Reserva.data_prevista_fim >= inicio),
        )
        .first()
        is not None
    )


def contar_do_usuario(db: Session, id_usuario: int, status: Optional[str] = None) -> int:
    consulta = db.query(Reserva).filter(
        or_(Reserva.id_locatario == id_usuario, Reserva.id_locador == id_usuario)
    )
    if status:
        consulta = consulta.filter(Reserva.status_reserva == status)
    return consulta.count()


def listar_por_ferramenta(db: Session, id_ferramenta: int) -> Sequence[Reserva]:
    return db.query(Reserva).filter(Reserva.id_ferramenta == id_ferramenta).all()


def criar_mensagem(db: Session, id_reserva: int, id_remetente: int, conteudo: str) -> Mensagem:
    mensagem = Mensagem(id_reserva=id_reserva, id_remetente=id_remetente, conteudo=conteudo)
    db.add(mensagem)
    db.commit()
    db.refresh(mensagem)
    return mensagem
