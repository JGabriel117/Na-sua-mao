"""Consultas de moderação: denúncias, avaliações e limpeza de anúncio."""

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from src.models.models import (
    Avaliacao,
    Contrato,
    Denuncia,
    Devolucao,
    Ferramenta,
    Mensagem,
    Reserva,
    Retirada,
)


def obter_denuncia(db: Session, id_denuncia: int) -> Optional[Denuncia]:
    return db.query(Denuncia).filter(Denuncia.id_denuncia == id_denuncia).first()


def listar_denuncias(db: Session, limite: int = 50, status: Optional[str] = None) -> Sequence[Denuncia]:
    consulta = db.query(Denuncia)
    if status:
        consulta = consulta.filter(Denuncia.status_denuncia == status)
    return consulta.order_by(Denuncia.created_at.desc()).limit(limite).all()


def contar_denuncias_abertas(db: Session) -> int:
    return db.query(Denuncia).filter(Denuncia.status_denuncia == "aberta").count()


def obter_avaliacao(db: Session, id_avaliacao: int) -> Optional[Avaliacao]:
    return db.query(Avaliacao).filter(Avaliacao.id_avaliacao == id_avaliacao).first()


def avaliacao_do_avaliador_na_reserva(db: Session, id_reserva: int, id_avaliador: int) -> Optional[Avaliacao]:
    return (
        db.query(Avaliacao)
        .filter(Avaliacao.id_reserva == id_reserva, Avaliacao.id_avaliador == id_avaliador)
        .first()
    )


def denuncia_aberta_duplicada(
    db: Session,
    id_denunciante: int,
    id_ferramenta: Optional[int],
    id_denunciado: Optional[int],
    id_avaliacao: Optional[int],
) -> bool:
    return (
        db.query(Denuncia.id_denuncia)
        .filter(
            Denuncia.id_denunciante == id_denunciante,
            Denuncia.status_denuncia == "aberta",
            Denuncia.id_ferramenta == id_ferramenta,
            Denuncia.id_denunciado == id_denunciado,
            Denuncia.id_avaliacao == id_avaliacao,
        )
        .first()
        is not None
    )


def desvincular_denuncias_da_ferramenta(db: Session, id_ferramenta: int) -> int:
    """Preserva a denúncia (histórico) e remove o vínculo com o anúncio excluído."""
    return (
        db.query(Denuncia)
        .filter(Denuncia.id_ferramenta == id_ferramenta)
        .update({Denuncia.id_ferramenta: None}, synchronize_session=False)
    )


def desvincular_denuncias_da_avaliacao(db: Session, id_avaliacao: int) -> int:
    return (
        db.query(Denuncia)
        .filter(Denuncia.id_avaliacao == id_avaliacao)
        .update({Denuncia.id_avaliacao: None}, synchronize_session=False)
    )


def purgar_dados_operacionais(db: Session, id_ferramenta: int) -> dict:
    """Remove reservas do anúncio e todos os registros dependentes.

    Retorna as contagens para a auditoria. O anúncio em si é removido pelo
    service depois de desvincular as denúncias.
    """
    ids_reservas = [r.id_reserva for r in db.query(Reserva.id_reserva).filter(Reserva.id_ferramenta == id_ferramenta).all()]
    contagens = {
        "reservas": len(ids_reservas),
        "mensagens": 0,
        "avaliacoes": 0,
        "contratos": 0,
        "retiradas": 0,
        "devolucoes": 0,
    }
    if ids_reservas:
        contagens["mensagens"] = (
            db.query(Mensagem).filter(Mensagem.id_reserva.in_(ids_reservas)).delete(synchronize_session=False)
        )
        ids_avaliacoes = [
            a.id_avaliacao for a in db.query(Avaliacao.id_avaliacao).filter(Avaliacao.id_reserva.in_(ids_reservas)).all()
        ]
        for id_avaliacao in ids_avaliacoes:
            desvincular_denuncias_da_avaliacao(db, id_avaliacao)
        contagens["avaliacoes"] = (
            db.query(Avaliacao).filter(Avaliacao.id_reserva.in_(ids_reservas)).delete(synchronize_session=False)
        )
        contagens["contratos"] = (
            db.query(Contrato).filter(Contrato.id_reserva.in_(ids_reservas)).delete(synchronize_session=False)
        )
        contagens["retiradas"] = (
            db.query(Retirada).filter(Retirada.id_reserva.in_(ids_reservas)).delete(synchronize_session=False)
        )
        contagens["devolucoes"] = (
            db.query(Devolucao).filter(Devolucao.id_reserva.in_(ids_reservas)).delete(synchronize_session=False)
        )
    desvincular_denuncias_da_ferramenta(db, id_ferramenta)
    db.query(Reserva).filter(Reserva.id_ferramenta == id_ferramenta).delete(synchronize_session=False)
    return contagens


def remover_ferramenta(db: Session, ferramenta: Ferramenta) -> None:
    db.delete(ferramenta)
    db.commit()


def listar_denuncias_contra(db: Session, id_usuario: int, limite: int = 30):
    return (
        db.query(Denuncia)
        .filter(Denuncia.id_denunciado == id_usuario)
        .order_by(Denuncia.created_at.desc())
        .limit(limite)
        .all()
    )


def listar_denuncias_feitas(db: Session, id_usuario: int, limite: int = 30):
    return (
        db.query(Denuncia)
        .filter(Denuncia.id_denunciante == id_usuario)
        .order_by(Denuncia.created_at.desc())
        .limit(limite)
        .all()
    )
