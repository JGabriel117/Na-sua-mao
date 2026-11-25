"""Inicializacao do banco de dados.

Uso:
    python -m scripts.init_db

- Em MySQL 8.0 cria a base (se ainda nao existir) com utf8mb4 e depois as tabelas.
- Em SQLite apenas cria o arquivo e as tabelas.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from database import DATABASE_URL, Base, engine  # noqa: E402
from src.models import models  # noqa: F401,E402  (registra as 11 tabelas no metadata)

TABELAS_ESPERADAS = [
    "usuarios",
    "categorias",
    "ferramentas",
    "reservas",
    "contratos",
    "retiradas",
    "devolucoes",
    "avaliacoes",
    "denuncias",
    "mensagens",
    "logs_auditoria",
]


COLUNAS_NOVAS = {
    "usuarios": [
        ("origem_localizacao", "VARCHAR(20)"),
        ("localizacao_atualizada_em", "DATETIME"),
    ],
    "ferramentas": [
        ("excluida_em", "DATETIME"),
    ],
    "denuncias": [
        ("id_avaliacao", "INTEGER"),
    ],
}


def _criar_base_mysql() -> None:
    """Cria o schema no MySQL, caso ele ainda não exista."""
    import re

    import pymysql

    url = make_url(DATABASE_URL)
    base = url.database or ""
    if not re.fullmatch(r"[A-Za-z0-9_]+", base):
        raise SystemExit(f"Nome de banco inválido em DATABASE_URL: {base!r}")

    try:
        conexao = pymysql.connect(
            host=url.host or "localhost",
            port=url.port or 3306,
            user=url.username or "root",
            password=url.password or "",
            charset="utf8mb4",
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            "Nao foi possivel conectar ao MySQL.\n"
            f"  DATABASE_URL atual: {DATABASE_URL}\n"
            f"  Detalhe: {exc}\n\n"
            "Verifique se o servidor MySQL 8.0 esta rodando e se usuario/senha do .env estao corretos.\n"
            "Para rodar sem MySQL, use no .env:  DATABASE_URL=sqlite:///./na_sua_mao.db"
        ) from exc

    try:
        with conexao.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{base}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conexao.commit()
    finally:
        conexao.close()


def _garantir_colunas() -> None:
    """Adiciona colunas novas em bancos já existentes (migracao leve, sem Alembic)."""
    inspetor = inspect(engine)
    existentes_tabelas = set(inspetor.get_table_names())
    with engine.begin() as conexao:
        for tabela, colunas in COLUNAS_NOVAS.items():
            if tabela not in existentes_tabelas:
                continue
            atuais = {coluna["name"] for coluna in inspetor.get_columns(tabela)}
            for nome, tipo in colunas:
                if nome in atuais:
                    continue
                conexao.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"))
                print(f"  [migrado] {tabela}.{nome}")


def executar() -> None:
    url = make_url(DATABASE_URL)
    if url.get_backend_name().startswith("mysql"):
        _criar_base_mysql()
    elif url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        caminho = Path(url.database)
        if not caminho.is_absolute():
            caminho = RAIZ / caminho
        caminho.parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)
    _garantir_colunas()

    existentes = set(inspect(engine).get_table_names())
    print(f"Banco: {DATABASE_URL}")
    for tabela in TABELAS_ESPERADAS:
        estado = "ok" if tabela in existentes else "AUSENTE"
        print(f"  [{estado}] {tabela}")
    print("Estrutura pronta. Próximo passo:  python -m scripts.seed")


if __name__ == "__main__":
    executar()
