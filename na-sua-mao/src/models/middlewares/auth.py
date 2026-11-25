"""Autenticacao JWT em cookie HttpOnly e controle de acesso por perfil."""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from src.models.models import Usuario

SECRET_KEY = os.getenv("SECRET_KEY", "na-sua-mao-dev-secret-altere-em-producao")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "240"))
COOKIE_NAME = "nsm_token"


def criar_token(usuario: Usuario) -> str:
    payload = {
        "sub": str(usuario.id_usuario),
        "email": usuario.email,
        "is_admin": usuario.is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decodificar_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def usuario_atual(request: Request, db: Session = Depends(get_db)) -> Optional[Usuario]:
    """Retorna o usuário da sessão ou None para visitantes."""
    request.state.usuario = None
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    dados = decodificar_token(token)
    if not dados:
        return None
    usuario = db.query(Usuario).filter(Usuario.id_usuario == int(dados.get("sub", 0))).first()
    if usuario and usuario.status_conta == "ativa":
        request.state.usuario = usuario
        return usuario
    return None


def require_user(request: Request, usuario: Optional[Usuario] = Depends(usuario_atual)) -> Usuario:
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticacao necessaria",
            headers={"Location": f"/login?next={request.url.path}"},
        )
    return usuario


def require_admin(usuario: Usuario = Depends(require_user)) -> Usuario:
    """RN06: rotas administrativas exigem is_admin = True."""
    if not usuario.is_admin:
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return usuario


def obter_ip(request: Request) -> str:
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def autenticar_cookie(response, usuario: Usuario) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=criar_token(usuario),
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
