"""Ponto de entrada da aplicacao Na Sua Mao (FastAPI)."""

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from database import Base, engine
from src.controllers import (
    admin_controller,
    auth_controller,
    ferramenta_controller,
    perfil_controller,
    reserva_controller,
)
from src.controllers._utils import render

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

app = FastAPI(title="Na Sua Mao", description="Economia colaborativa de ferramentas entre vizinhos", version="1.0.0")

Path("static/uploads").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

Base.metadata.create_all(bind=engine)

app.include_router(auth_controller.router)
app.include_router(perfil_controller.router)
app.include_router(ferramenta_controller.router)
app.include_router(reserva_controller.router)
app.include_router(admin_controller.router)


@app.exception_handler(RequestValidationError)
async def tratar_validacao(request: Request, exc: RequestValidationError):
    """Impede que o usuario veja o JSON cru 422 do FastAPI."""
    campos = ", ".join(str(erro.get("loc", ["?"])[-1]) for erro in exc.errors())[:200]
    return render(
        request,
        "erro.html",
        None,
        status_code=400,
        codigo=400,
        detalhe=f"Dados invalidos no formulario ({campos}). Volte e verifique os campos.",
    )


@app.exception_handler(Exception)
async def tratar_erro_interno(request: Request, exc: Exception):
    """Ultimo recurso: nunca mostra traceback ao usuario."""
    import logging

    logging.getLogger("na_sua_mao").exception("Erro nao tratado em %s", request.url.path)
    return render(
        request,
        "erro.html",
        None,
        status_code=500,
        codigo=500,
        detalhe="Algo saiu do esperado do nosso lado. Tente novamente em alguns instantes.",
    )


@app.exception_handler(StarletteHTTPException)
async def tratar_http_exception(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        destino = exc.headers.get("Location", "/login") if exc.headers else "/login"
        return RedirectResponse(f"/login?next={destino}", status_code=303)
    return render(
        request, "erro.html", None, status_code=exc.status_code, codigo=exc.status_code, detalhe=str(exc.detail)
    )


@app.get("/health")
def health():
    return {"status": "ok", "app": "Na Sua Mao"}
