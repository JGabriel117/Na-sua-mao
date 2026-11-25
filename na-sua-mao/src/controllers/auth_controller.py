"""Rotas de autenticação: login, cadastro e logout."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from src.controllers._utils import render, voltar_para
from src.integrations import geocoding_service
from src.middlewares.auth import autenticar_cookie, obter_ip, usuario_atual
from src.services import auditoria_service, usuario_service
from src.services.usuario_service import ErroValidacao

router = APIRouter(tags=["autenticacao"])


@router.get("/login")
def tela_login(request: Request, usuario=Depends(usuario_atual)):
    if usuario:
        return RedirectResponse("/painel", status_code=303)
    return render(request, "login.html", usuario, proximo=request.query_params.get("next", "/painel"))


@router.post("/login")
def login(
    request: Request,
    email: str = Form(""),
    senha: str = Form(""),
    proximo: str = Form("/painel"),
    db: Session = Depends(get_db),
):
    try:
        usuario = usuario_service.autenticar(db, email, senha)
    except ErroValidacao as exc:
        auditoria_service.registrar(
            db, None, "LOGIN_FALHA", f"Tentativa de login malsucedida para {email or '(vazio)'}", obter_ip(request)
        )
        return render(request, "login.html", None, erro=str(exc), email=email, proximo=proximo)

    auditoria_service.registrar(db, usuario.id_usuario, "LOGIN", f"Login realizado por {usuario.email}", obter_ip(request))

    destino = proximo if proximo.startswith("/") else "/painel"
    if usuario.is_admin:
        destino = "/admin"

    resposta = RedirectResponse(destino, status_code=303)
    autenticar_cookie(resposta, usuario)
    return resposta


@router.get("/cadastro")
def tela_cadastro(request: Request, usuario=Depends(usuario_atual)):
    if usuario:
        return RedirectResponse("/painel", status_code=303)
    return render(request, "cadastro.html", usuario)


@router.post("/cadastro")
def cadastrar(
    request: Request,
    nome: str = Form(""),
    email: str = Form(""),
    cpf: str = Form(""),
    cep: str = Form(""),
    senha: str = Form(""),
    confirmacao: str = Form(""),
    lgpd: str = Form(None),
    db: Session = Depends(get_db),
):
    dados = {"nome": nome, "email": email, "cpf": cpf, "cep": cep}

    if not lgpd:
        return render(request, "cadastro.html", None, erro="E necessario aceitar os Termos de Uso e a Politica de Privacidade (LGPD).", **dados)

    try:
        usuario = usuario_service.criar_usuario(db, nome, email, cpf, senha, confirmacao, cep)
    except ErroValidacao as exc:
        return render(request, "cadastro.html", None, erro=str(exc), **dados)

    # CEP informado no cadastro ja define a regiao (usuario nunca digita coordenadas).
    if usuario.cep:
        try:
            latitude, longitude, _ = geocoding_service.coordenadas_por_cep(usuario.cep)
        except LookupError:
            pass
        else:
            usuario_service.definir_localizacao(db, usuario, latitude, longitude, "cep")

    auditoria_service.registrar(
        db, usuario.id_usuario, "CADASTRO_USUARIO", f"Conta criada para {usuario.email} (CPF {usuario.cpf})", obter_ip(request)
    )

    resposta = RedirectResponse("/painel?msg=Conta+criada+com+sucesso.+Bem-vindo+à+vizinhança!", status_code=303)
    autenticar_cookie(resposta, usuario)
    return resposta


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db), usuario=Depends(usuario_atual)):
    if usuario:
        auditoria_service.registrar(db, usuario.id_usuario, "LOGOUT", f"Sessão encerrada por {usuario.email}", obter_ip(request))
    resposta = voltar_para("/login", "Sessão encerrada com sucesso.")
    resposta.delete_cookie("nsm_token")
    return resposta


@router.get("/recuperar-senha")
def tela_recuperar_senha(request: Request, usuario=Depends(usuario_atual)):
    return render(request, "recuperar_senha.html", usuario)


@router.post("/recuperar-senha")
def recuperar_senha(
    request: Request,
    email: str = Form(""),
    cpf: str = Form(""),
    nova_senha: str = Form(""),
    confirmacao: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        usuario = usuario_service.recuperar_senha(db, email, cpf, nova_senha, confirmacao)
    except ErroValidacao as exc:
        auditoria_service.registrar(
            db, None, "RECUPERACAO_SENHA_FALHA",
            f"Tentativa de recuperação malsucedida para {email or '(vazio)'}", obter_ip(request),
        )
        return render(
            request, "recuperar_senha.html", None,
            erro=str(exc), email=email, cpf=cpf,
        )

    auditoria_service.registrar(
        db, usuario.id_usuario, "RECUPERACAO_SENHA",
        f"Senha redefinida pelo fluxo de recuperação para {usuario.email}", obter_ip(request),
    )
    return voltar_para("/login", "Senha redefinida com sucesso. Entre com a nova senha.")
