from datetime import datetime
from sqlalchemy import Column, Integer, Text, TIMESTAMP, ForeignKey
from sqlalchemy.orm import Session
from database import Base

class Avaliacao(Base):
    __tablename__ = "avaliacoes"

    id_avaliacao = Column(Integer, primary_key=True, autoincrement=True)
    id_reserva = Column(Integer, ForeignKey("reservas.id_reserva"), nullable=False)
    id_avaliador = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_avaliado = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    nota = Column(Integer, nullable=False)
    comentario = Column(Text, nullable=True)
    data_avaliacao = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)


def salvar_avaliacao(db: Session, id_reserva: int, id_avaliador: int, id_avaliado: int, nota: int, comentario: str):
    nova_avaliacao = Avaliacao(
        id_reserva=id_reserva,
        id_avaliador=id_avaliador,
        id_avaliado=id_avaliado,
        nota=nota,
        comentario=comentario
    )
    db.add(nova_avaliacao)
    db.commit()
    db.refresh(nova_avaliacao)
    return nova_avaliacao.id_avaliacao



def buscar_avaliacoes_por_usuario(db: Session, id_avaliado: int):
    return db.query(Avaliacao).filter(Avaliacao.id_avaliado == id_avaliado).all()