"""Sobe a aplicacao em modo de desenvolvimento.

Uso:
    python run.py

Variaveis opcionais no .env:
    HOST=127.0.0.1
    PORT=8000
    RELOAD=true
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
os.chdir(RAIZ)
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    porta = int(os.getenv("PORT", "8000"))
    recarregar = os.getenv("RELOAD", "true").strip().lower() in {"1", "true", "sim", "yes"}

    print(f"Na Sua Mao rodando em http://{host}:{porta}  (Ctrl+C para parar)")
    uvicorn.run("main:app", host=host, port=porta, reload=recarregar)
