"""Servico transversal de auditoria (RN08 / RNF04).

Toda acao sensivel e gravada em `logs_auditoria` com ator (usuario_id),
endereco IP de origem e timestamp gerado pelo banco/aplicacao. O registro e
somente-insercao: nenhuma rotina da aplicacao altera ou remove logs.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.models.models import LogAuditoria
from src.repositories import auditoria_repository

log = logging.getLogger("na_sua_mao.auditoria")


def registrar(
    db: Session,
    usuario_id: Optional[int],
    acao: str,
    detalhe: str = "",
    ip: Optional[str] = None,
) -> Optional[LogAuditoria]:
    """Grava uma linha imutavel em logs_auditoria com IP, ator e timestamp.

    A auditoria nunca deve derrubar a acao principal: se a gravacao falhar, o
    erro e registrado no log da aplicacao e a operacao do usuario continua.
    """
    registro = LogAuditoria(
        usuario_id=usuario_id,
        acao=(acao or "ACAO_NAO_IDENTIFICADA")[:120],
        detalhe=(detalhe or "")[:2000] or None,
        ip=(ip or None) and ip[:45],
    )
    try:
        db.add(registro)
        db.commit()
        db.refresh(registro)
        return registro
    except Exception:  # noqa: BLE001 - auditoria nunca interrompe o fluxo
        log.exception("Falha ao gravar log de auditoria da acao %s", acao)
        db.rollback()
        return None


def listar(db: Session, limite: int = 100):
    return auditoria_repository.listar(db, limite=limite)


def listar_do_usuario(db: Session, usuario_id: int, limite: int = 50):
    return auditoria_repository.listar_do_usuario(db, usuario_id, limite=limite)
