"""Consultas de ferramentas e avaliações."""

from typing import Optional, Sequence

from sqlalchemy.orm import Query, Session

from src.models.models import Avaliacao, Categoria, Ferramenta, Reserva, Usuario

STATUS_OCULTOS_CATALOGO = ("excluida", "suspensa")


def listar_categorias(db: Session):
    return db.query(Categoria).order_by(Categoria.nome).all()


def obter(db: Session, id_ferramenta: int) -> Optional[Ferramenta]:
    return db.query(Ferramenta).filter(Ferramenta.id_ferramenta == id_ferramenta).first()


def consulta_catalogo(db: Session) -> Query:
    """Base do catálogo: apenas anúncios públicos, com categoria e locador."""
    return (
        db.query(Ferramenta)
        .outerjoin(Categoria, Ferramenta.id_categoria == Categoria.id_categoria)
        .join(Usuario, Ferramenta.id_locador == Usuario.id_usuario)
        .filter(
            Ferramenta.status_ferramenta.notin_(STATUS_OCULTOS_CATALOGO),
            Ferramenta.excluida_em.is_(None),
        )
    )


def listar_do_locador(db: Session, id_locador: int, incluir_excluidas: bool = False) -> Sequence[Ferramenta]:
    consulta = db.query(Ferramenta).filter(Ferramenta.id_locador == id_locador)
    if not incluir_excluidas:
        consulta = consulta.filter(
            Ferramenta.status_ferramenta != "excluida",
            Ferramenta.excluida_em.is_(None),
        )
    return consulta.order_by(Ferramenta.created_at.desc()).all()


def contar_do_locador(db: Session, id_locador: int) -> int:
    return db.query(Ferramenta).filter(Ferramenta.id_locador == id_locador).count()


def contar_publicas(db: Session) -> int:
    return (
        db.query(Ferramenta)
        .filter(
            Ferramenta.status_ferramenta.notin_(STATUS_OCULTOS_CATALOGO),
            Ferramenta.excluida_em.is_(None),
        )
        .count()
    )


def primeira_reserva_com_status(db: Session, id_ferramenta: int, status: Sequence[str]) -> Optional[Reserva]:
    return (
        db.query(Reserva)
        .filter(Reserva.id_ferramenta == id_ferramenta, Reserva.status_reserva.in_(status))
        .first()
    )


def avaliacoes_recebidas(db: Session, id_usuario: int):
    return (
        db.query(Avaliacao)
        .filter(Avaliacao.id_avaliado == id_usuario)
        .order_by(Avaliacao.created_at.desc())
        .all()
    )


def avaliacoes_da_ferramenta(db: Session, id_ferramenta: int):
    return (
        db.query(Avaliacao)
        .join(Reserva, Avaliacao.id_reserva == Reserva.id_reserva)
        .filter(Reserva.id_ferramenta == id_ferramenta)
        .order_by(Avaliacao.created_at.desc())
        .all()
    )
