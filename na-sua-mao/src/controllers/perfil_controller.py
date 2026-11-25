"""Rotas de gerenciamento do perfil do usuario autenticado.

A localizacao e sempre obtida do navegador ou estimada pelo CEP cadastrado:
o usuario nunca digita coordenadas.
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from database import get_db
from src.controllers._utils import render, voltar_para
from src.integrations import geocoding_service
from src.middlewares.auth import obter_ip, require_user
from src.services import auditoria_service, ferramenta_service, usuario_service
from src.services.usuario_service import ErroValidacao

router = APIRouter(tags=["perfil"])


def _contexto(db: Session, usuario) -> dict:
    return {
        "stats": usuario_service.estatisticas_usuario(db, usuario),
        "avaliacoes_recebidas": ferramenta_service.avaliacoes_recebidas(db, usuario.id_usuario),
    }


@router.get("/perfil")
def tela_perfil(request: Request, db: Session = Depends(get_db), usuario=Depends(require_user)):
    return render(request, "perfil.html", usuario, **_contexto(db, usuario))


@router.post("/perfil")
def salvar_perfil(
    request: Request,
    nome: str = Form(""),
    email: str = Form(""),
    cep: str = Form(""),
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    cep_anterior = usuario.cep

    try:
        usuario = usuario_service.atualizar_perfil(db, usuario, nome, email, cep)
    except ErroValidacao as exc:
        return render(
            request,
            "perfil.html",
            usuario,
            erro=str(exc),
            form={"nome": nome, "email": email, "cep": cep},
            **_contexto(db, usuario),
        )

    mensagem = "Dados do perfil atualizados com sucesso."
    tipo = "sucesso"

    # CEP novo/alterado (ou usuario ainda sem localizacao) -> estima a posicao pelo CEP.
    if usuario.cep and (usuario.cep != cep_anterior or usuario.latitude is None):
        try:
            latitude, longitude, _ = geocoding_service.coordenadas_por_cep(usuario.cep)
        except LookupError:
            mensagem = "Dados atualizados. Não conseguimos localizar seu CEP agora; tente novamente em alguns minutos."
            tipo = "erro"
        else:
            usuario = usuario_service.definir_localizacao(db, usuario, latitude, longitude, "cep")
            auditoria_service.registrar(
                db, usuario.id_usuario, "ATUALIZACAO_LOCALIZACAO_CEP",
                f"Localização estimada pelo CEP {usuario.cep}", obter_ip(request),
            )
            mensagem = "Dados atualizados. Localizamos sua região pelo CEP."

    # CEP removido e a localizacao vinha dele -> deixa de ter localizacao.
    elif not usuario.cep and usuario.origem_localizacao == "cep":
        usuario_service.limpar_localizacao(db, usuario)
        mensagem = "Dados atualizados. Sua localização anterior foi removida."

    auditoria_service.registrar(
        db, usuario.id_usuario, "ATUALIZACAO_PERFIL",
        f"Dados atualizados: {usuario.nome} <{usuario.email}>", obter_ip(request),
    )
    return voltar_para("/perfil", mensagem, tipo)


def _destino_seguro(destino: str) -> str:
    return destino if destino.startswith("/") else "/"


@router.post("/perfil/localizacao")
def salvar_localizacao(
    request: Request,
    latitude: str = Form(""),
    longitude: str = Form(""),
    destino: str = Form("/"),
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    """Coordenadas capturadas pelo navegador (navigator.geolocation)."""
    volta = _destino_seguro(destino)
    try:
        usuario = usuario_service.definir_localizacao(db, usuario, latitude, longitude, "navegador")
    except ErroValidacao as exc:
        return voltar_para(volta, str(exc), "erro")

    auditoria_service.registrar(
        db, usuario.id_usuario, "ATUALIZACAO_LOCALIZACAO",
        f"Coordenadas do navegador: {usuario.latitude}, {usuario.longitude}", obter_ip(request),
    )
    return voltar_para(volta, "Tudo certo! Agora mostramos ferramentas perto de você.")


@router.post("/perfil/localizacao/cep")
def localizar_por_cep(
    request: Request,
    destino: str = Form("/"),
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    """Fallback: estima a posição a partir do CEP quando o navegador não e autorizado."""
    volta = _destino_seguro(destino)
    if not usuario.cep:
        return voltar_para(
            "/perfil", "Cadastre seu CEP para usarmos a busca por perto.", "erro"
        )

    try:
        latitude, longitude, _ = geocoding_service.coordenadas_por_cep(usuario.cep)
    except LookupError as exc:
        return voltar_para(volta, str(exc), "erro")

    usuario = usuario_service.definir_localizacao(db, usuario, latitude, longitude, "cep")
    auditoria_service.registrar(
        db, usuario.id_usuario, "ATUALIZACAO_LOCALIZACAO_CEP",
        f"Localização estimada pelo CEP {usuario.cep}: {usuario.latitude}, {usuario.longitude}",
        obter_ip(request),
    )
    return voltar_para(volta, "Localizamos sua região pelo CEP. Busca por perto ativada.")


@router.post("/perfil/senha")
def trocar_senha(
    request: Request,
    senha_atual: str = Form(""),
    nova_senha: str = Form(""),
    confirmacao: str = Form(""),
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    try:
        usuario_service.alterar_senha(db, usuario, senha_atual, nova_senha, confirmacao)
    except ErroValidacao as exc:
        return render(
            request, "perfil.html", usuario,
            erro_senha=str(exc), aba="seguranca", **_contexto(db, usuario),
        )

    auditoria_service.registrar(
        db, usuario.id_usuario, "ALTERACAO_SENHA", f"Senha alterada por {usuario.email}", obter_ip(request)
    )
    return voltar_para("/perfil", "Senha alterada com sucesso.")
