"""Consultas de logs de auditoria."""

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.models.models import LogAuditoria


def listar(db: Session, limite: int = 100):
    return db.query(LogAuditoria).order_by(desc(LogAuditoria.created_at)).limit(limite).all()


def listar_do_usuario(db: Session, usuario_id: int, limite: int = 50):
    return (
        db.query(LogAuditoria)
        .filter(LogAuditoria.usuario_id == usuario_id)
        .order_by(desc(LogAuditoria.created_at))
        .limit(limite)
        .all()
    )
