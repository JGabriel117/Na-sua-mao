"""Consultas de usuários."""

from typing import Optional

from sqlalchemy.orm import Session

from src.models.models import Usuario


def buscar_por_id(db: Session, id_usuario: int) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()


def buscar_por_email(db: Session, email: str) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.email == (email or "").strip().lower()).first()


def buscar_por_cpf(db: Session, cpf: str) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.cpf == cpf).first()


def email_em_uso(db: Session, email: str, ignorar_id: Optional[int] = None) -> bool:
    consulta = db.query(Usuario.id_usuario).filter(Usuario.email == email)
    if ignorar_id:
        consulta = consulta.filter(Usuario.id_usuario != ignorar_id)
    return consulta.first() is not None


def cpf_em_uso(db: Session, cpf: str) -> bool:
    return db.query(Usuario.id_usuario).filter(Usuario.cpf == cpf).first() is not None


def listar_admins(db: Session):
    return db.query(Usuario).filter(Usuario.is_admin.is_(True)).order_by(Usuario.created_at).all()


def contar(db: Session, somente_admin: Optional[bool] = None) -> int:
    consulta = db.query(Usuario)
    if somente_admin is True:
        consulta = consulta.filter(Usuario.is_admin.is_(True))
    elif somente_admin is False:
        consulta = consulta.filter(Usuario.is_admin.is_(False))
    return consulta.count()
