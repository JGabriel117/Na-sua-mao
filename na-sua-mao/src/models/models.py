"""Mapeamento ORM das 11 tabelas da aplicação Na Sua Mao."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(160), unique=True, nullable=False, index=True)
    cpf = Column(String(14), unique=True, nullable=False, index=True)
    cep = Column(String(9), nullable=True)
    senha = Column(String(255), nullable=False)
    status_conta = Column(String(20), nullable=False, default="ativa")
    is_admin = Column(Boolean, nullable=False, default=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    origem_localizacao = Column(String(20), nullable=True)  # navegador | cep | manual
    localizacao_atualizada_em = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    ferramentas = relationship(
        "Ferramenta",
        back_populates="locador",
        cascade="all, delete-orphan",
        foreign_keys="Ferramenta.id_locador",
    )


class Categoria(Base):
    __tablename__ = "categorias"

    id_categoria = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(80), unique=True, nullable=False)
    descricao = Column(String(255), nullable=True)

    ferramentas = relationship("Ferramenta", back_populates="categoria")


class Ferramenta(Base):
    __tablename__ = "ferramentas"

    id_ferramenta = Column(Integer, primary_key=True, autoincrement=True)
    id_locador = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_categoria = Column(Integer, ForeignKey("categorias.id_categoria"), nullable=False)
    titulo = Column(String(140), nullable=False)
    descricao = Column(Text, nullable=True)
    voltagem = Column(String(20), nullable=True)
    estado_conservacao = Column(String(40), nullable=True)
    preco_diaria = Column(Numeric(10, 2), nullable=False, default=0)
    status_ferramenta = Column(String(20), nullable=False, default="disponivel")
    foto1 = Column(String(255), nullable=True)
    foto2 = Column(String(255), nullable=True)
    foto3 = Column(String(255), nullable=True)
    foto4 = Column(String(255), nullable=True)
    foto5 = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    # Soft delete: o anuncio sai do catalogo sem apagar o historico de reservas.
    excluida_em = Column(DateTime, nullable=True)

    locador = relationship("Usuario", back_populates="ferramentas", foreign_keys=[id_locador])
    categoria = relationship("Categoria", back_populates="ferramentas")
    reservas = relationship("Reserva", back_populates="ferramenta")

    @property
    def foto_principal(self):
        return self.foto1 or self.foto2 or self.foto3 or self.foto4 or self.foto5

    @property
    def fotos_lista(self):
        """Todas as fotos cadastradas, na ordem, sem lacunas."""
        return [f for f in (self.foto1, self.foto2, self.foto3, self.foto4, self.foto5) if f]

    @property
    def excluida(self):
        return self.status_ferramenta == "excluida" or self.excluida_em is not None

    @property
    def publica(self):
        """Anuncio visivel no catalogo publico (nao excluido nem suspenso)."""
        return self.status_ferramenta not in ("excluida", "suspensa") and self.excluida_em is None


class Reserva(Base):
    __tablename__ = "reservas"

    id_reserva = Column(Integer, primary_key=True, autoincrement=True)
    id_locatario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_locador = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_ferramenta = Column(Integer, ForeignKey("ferramentas.id_ferramenta"), nullable=False)
    data_prevista_inicio = Column(Date, nullable=False)
    data_prevista_fim = Column(Date, nullable=False)
    valor_total_calculado = Column(Numeric(10, 2), nullable=False, default=0)
    status_reserva = Column(String(20), nullable=False, default="pendente")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    locatario = relationship("Usuario", foreign_keys=[id_locatario])
    locador = relationship("Usuario", foreign_keys=[id_locador])
    ferramenta = relationship("Ferramenta", back_populates="reservas")
    contrato = relationship("Contrato", back_populates="reserva", uselist=False)
    retirada = relationship("Retirada", back_populates="reserva", uselist=False)
    devolucao = relationship("Devolucao", back_populates="reserva", uselist=False)
    mensagens = relationship("Mensagem", back_populates="reserva", order_by="Mensagem.created_at")


class Contrato(Base):
    __tablename__ = "contratos"

    id_contrato = Column(Integer, primary_key=True, autoincrement=True)
    id_reserva = Column(Integer, ForeignKey("reservas.id_reserva"), unique=True, nullable=False)
    conteudo = Column(Text, nullable=False)
    hash_seguranca = Column(String(64), nullable=False)
    aceite_locatario = Column(Boolean, nullable=False, default=False)
    aceite_locador = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    reserva = relationship("Reserva", back_populates="contrato")


class Retirada(Base):
    __tablename__ = "retiradas"

    id_retirada = Column(Integer, primary_key=True, autoincrement=True)
    id_reserva = Column(Integer, ForeignKey("reservas.id_reserva"), nullable=False)
    data_retirada = Column(DateTime, nullable=False, default=datetime.utcnow)
    confirmado_por = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=True)
    observacao = Column(Text, nullable=True)

    reserva = relationship("Reserva", back_populates="retirada")


class Devolucao(Base):
    __tablename__ = "devolucoes"

    id_devolucao = Column(Integer, primary_key=True, autoincrement=True)
    id_reserva = Column(Integer, ForeignKey("reservas.id_reserva"), nullable=False)
    data_devolucao = Column(DateTime, nullable=False, default=datetime.utcnow)
    estado_equipamento = Column(String(60), nullable=True)
    taxa_atraso = Column(Numeric(10, 2), nullable=False, default=0)
    observacao = Column(Text, nullable=True)

    reserva = relationship("Reserva", back_populates="devolucao")


class Avaliacao(Base):
    __tablename__ = "avaliacoes"

    id_avaliacao = Column(Integer, primary_key=True, autoincrement=True)
    id_reserva = Column(Integer, ForeignKey("reservas.id_reserva"), nullable=False)
    id_avaliador = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_avaliado = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    nota = Column(Integer, nullable=False, default=5)
    comentario = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    avaliador = relationship("Usuario", foreign_keys=[id_avaliador])
    avaliado = relationship("Usuario", foreign_keys=[id_avaliado])


class Denuncia(Base):
    __tablename__ = "denuncias"

    id_denuncia = Column(Integer, primary_key=True, autoincrement=True)
    id_denunciante = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_denunciado = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=True)
    id_ferramenta = Column(Integer, ForeignKey("ferramentas.id_ferramenta"), nullable=True)
    id_avaliacao = Column(Integer, ForeignKey("avaliacoes.id_avaliacao"), nullable=True)
    motivo = Column(String(120), nullable=False)
    descricao = Column(Text, nullable=True)
    status_denuncia = Column(String(20), nullable=False, default="aberta")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    denunciante = relationship("Usuario", foreign_keys=[id_denunciante])
    denunciado = relationship("Usuario", foreign_keys=[id_denunciado])
    ferramenta = relationship("Ferramenta", foreign_keys=[id_ferramenta])
    avaliacao = relationship("Avaliacao", foreign_keys=[id_avaliacao])


class Mensagem(Base):
    __tablename__ = "mensagens"

    id_mensagem = Column(Integer, primary_key=True, autoincrement=True)
    id_reserva = Column(Integer, ForeignKey("reservas.id_reserva"), nullable=False)
    id_remetente = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    conteudo = Column(Text, nullable=False)
    lida = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    reserva = relationship("Reserva", back_populates="mensagens")
    remetente = relationship("Usuario")


class LogAuditoria(Base):
    __tablename__ = "logs_auditoria"

    id_log = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=True)
    acao = Column(String(120), nullable=False)
    detalhe = Column(Text, nullable=True)
    ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    usuario = relationship("Usuario")
