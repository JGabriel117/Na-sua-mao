"""Rotas administrativas: painel de gestão, moderação, cadastro de admins e auditoria."""

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from database import get_db
from src.controllers._utils import render, voltar_para
from src.middlewares.auth import obter_ip, require_admin
from src.services import auditoria_service, moderacao_service, usuario_service
from src.services.usuario_service import ErroValidacao

router = APIRouter(prefix="/admin", tags=["administracao"])


@router.get("")
def painel_admin(request: Request, db: Session = Depends(get_db), admin=Depends(require_admin)):
    denuncias = moderacao_service.listar_denuncias(db, limite=100)
    abertas = [d for d in denuncias if d.status_denuncia == moderacao_service.STATUS_DENUNCIA_ABERTA]
    resolvidas = [d for d in denuncias if d.status_denuncia != moderacao_service.STATUS_DENUNCIA_ABERTA]

    return render(
        request,
        "painel_admin.html",
        admin,
        **moderacao_service.estatisticas_painel(db),
        logs=auditoria_service.listar(db, limite=40),
        denuncias_abertas=abertas,
        denuncias_resolvidas=resolvidas,
        admins=usuario_service.listar_admins(db),
    )


@router.get("/usuarios/{id_usuario}")
def detalhe_usuario_admin(
    request: Request,
    id_usuario: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    try:
        contexto = moderacao_service.dados_moderacao_usuario(db, id_usuario)
    except ErroValidacao as exc:
        return voltar_para("/admin", str(exc), "erro")

    return render(
        request,
        "admin_usuario.html",
        admin,
        **contexto,
        logs=auditoria_service.listar_do_usuario(db, id_usuario, limite=20),
    )


@router.get("/cadastrar")
def tela_cadastrar_admin(request: Request, admin=Depends(require_admin)):
    return render(request, "cadastrar_admin.html", admin)


@router.post("/cadastrar")
def cadastrar_admin(
    request: Request,
    nome: str = Form(""),
    email: str = Form(""),
    cpf: str = Form(""),
    senha: str = Form(""),
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    try:
        novo = usuario_service.criar_admin(db, nome, email, cpf, senha)
    except ErroValidacao as exc:
        return render(request, "cadastrar_admin.html", admin, erro=str(exc), form={"nome": nome, "email": email, "cpf": cpf})

    auditoria_service.registrar(
        db, admin.id_usuario, "CADASTRO_ADMIN",
        f"Novo administrador criado: {novo.email} (CPF {novo.cpf}) por {admin.email}", obter_ip(request),
    )
    return voltar_para("/admin", f"Administrador {novo.nome} cadastrado com sucesso.")


@router.post("/denuncias/{id_denuncia}/aprovar")
def aprovar_denuncia(
    request: Request,
    id_denuncia: int,
    observacao: str = Form(""),
    suspender_anuncio: str = Form(None),
    suspender_usuario: str = Form(None),
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    try:
        denuncia = moderacao_service.resolver_denuncia(
            db, id_denuncia, moderacao_service.STATUS_DENUNCIA_PROCEDENTE
        )
        id_ferramenta = denuncia.id_ferramenta
        id_denunciado = denuncia.id_denunciado
        if observacao.strip():
            moderacao_service.registrar_aviso_moderacao(db, id_denuncia, observacao)

        if suspender_anuncio and id_ferramenta:
            resultado = moderacao_service.remover_anuncio_por_denuncia(db, id_ferramenta)
            auditoria_service.registrar(
                db, admin.id_usuario, "MODERACAO_REMOCAO_ANUNCIO",
                (
                    f"Denúncia #{id_denuncia}: anúncio #{id_ferramenta} ({resultado['titulo']}) removido. "
                    f"Reservas: {resultado['reservas']}, mensagens: {resultado['mensagens']}, "
                    f"avaliações: {resultado['avaliacoes']}, contratos: {resultado['contratos']}, "
                    f"retiradas: {resultado['retiradas']}, devoluções: {resultado['devolucoes']}."
                ),
                obter_ip(request),
            )
        if suspender_usuario and id_denunciado:
            moderacao_service.suspender_usuario(db, id_denunciado)
            auditoria_service.registrar(
                db, admin.id_usuario, "SUSPENSAO_USUARIO",
                f"Usuário #{id_denunciado} suspenso pela denúncia #{id_denuncia}", obter_ip(request),
            )
    except ErroValidacao as exc:
        return voltar_para("/admin", str(exc), "erro")

    auditoria_service.registrar(
        db, admin.id_usuario, "APROVACAO_DENUNCIA",
        f"Denúncia #{id_denuncia} considerada procedente por {admin.email}", obter_ip(request),
    )
    return voltar_para("/admin", "Denúncia aprovada e medidas de moderação aplicadas.")


@router.post("/denuncias/{id_denuncia}/rejeitar")
def rejeitar_denuncia(
    request: Request,
    id_denuncia: int,
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    try:
        moderacao_service.resolver_denuncia(
            db, id_denuncia, moderacao_service.STATUS_DENUNCIA_IMPROCEDENTE
        )
        if observacao.strip():
            moderacao_service.registrar_aviso_moderacao(db, id_denuncia, observacao)
    except ErroValidacao as exc:
        return voltar_para("/admin", str(exc), "erro")

    auditoria_service.registrar(
        db, admin.id_usuario, "REJEICAO_DENUNCIA",
        f"Denúncia #{id_denuncia} considerada improcedente por {admin.email}", obter_ip(request),
    )
    return voltar_para("/admin", "Denúncia rejeitada.")


@router.post("/usuarios/{id_usuario}/status")
def alternar_status(request: Request, id_usuario: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    usuario = usuario_service.buscar_por_id(db, id_usuario)
    if not usuario:
        return voltar_para("/admin", "Usuário não encontrado.", "erro")
    if usuario.is_admin:
        return voltar_para("/admin", "Contas administrativas não podem ser suspensas por esta tela.", "erro")

    if usuario.status_conta == "ativa":
        moderacao_service.suspender_usuario(db, id_usuario)
        acao = "SUSPENSAO_USUARIO"
        mensagem = f"A conta de {usuario.nome} foi suspensa."
    else:
        moderacao_service.reativar_usuario(db, id_usuario)
        acao = "REATIVACAO_USUARIO"
        mensagem = f"A conta de {usuario.nome} foi reativada."

    auditoria_service.registrar(
        db, admin.id_usuario, acao,
        f"Conta {usuario.email} -> {usuario.status_conta} por {admin.email}", obter_ip(request),
    )
    return voltar_para(f"/admin/usuarios/{id_usuario}", mensagem)
