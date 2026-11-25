"""Configuracao de conexao com o banco de dados (SQLAlchemy 2.0).

Por padrao utiliza SQLite para execucao local imediata. Para MySQL 8.0 basta
definir a variavel DATABASE_URL no arquivo .env, por exemplo:
    DATABASE_URL=mysql+pymysql://usuario:senha@localhost:3306/na_sua_mao
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./na_sua_mao.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

Base = declarative_base()


def get_db():
    """Dependency do FastAPI que entrega uma sessao por requisicao."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
