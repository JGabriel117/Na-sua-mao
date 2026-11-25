"""Rotas de reservas, contrato, devolução, avaliação e chat."""

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from database import get_db
from src.controllers._utils import render, voltar_para
from src.middlewares.auth import obter_ip, require_user
from src.services import auditoria_service, ferramenta_service, moderacao_service, reserva_service
from src.services.usuario_service import ErroValidacao

router = APIRouter(tags=["reservas"])


def _carregar(db: Session, id_reserva: int):
    """Devolve (reserva, None) ou (None, resposta de erro pronta)."""
    try:
        return reserva_service.obter(db, id_reserva), None
    except ErroValidacao as exc:
        return None, voltar_para("/painel", str(exc), "erro")


@router.post("/reservas")
def solicitar_reserva(
    request: Request,
    id_ferramenta: int = Form(...),
    data_inicio: str = Form(""),
    data_fim: str = Form(""),
    aceite_termo: str = Form(None),
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    ferramenta = ferramenta_service.obter(db, id_ferramenta)
    try:
        reserva = reserva_service.solicitar_reserva(
            db, usuario, ferramenta, data_inicio, data_fim, bool(aceite_termo)
        )
    except ErroValidacao as exc:
        return voltar_para(f"/ferramentas/{id_ferramenta}", str(exc), "erro")

    auditoria_service.registrar(
        db, usuario.id_usuario, "SOLICITACAO_RESERVA",
        f"Reserva #{reserva.id_reserva} da ferramenta #{id_ferramenta} "
        f"({reserva.data_prevista_inicio} a {reserva.data_prevista_fim}) com aceite do termo",
        obter_ip(request),
    )
    return voltar_para("/painel", "Solicitação enviada ao proprietário. Acompanhe pelo painel.")


@router.post("/reservas/{id_reserva}/aprovar")
def aprovar(request: Request, id_reserva: int, db: Session = Depends(get_db), usuario=Depends(require_user)):
    reserva, erro = _carregar(db, id_reserva)
    if erro:
        return erro
    try:
        reserva_service.aprovar(db, reserva, usuario)
    except ErroValidacao as exc:
        return voltar_para("/painel", str(exc), "erro")
    auditoria_service.registrar(db, usuario.id_usuario, "APROVACAO_RESERVA", f"Reserva #{id_reserva} aprovada", obter_ip(request))
    return voltar_para("/painel", "Reserva aprovada. Combine a retirada pelo chat.")


@router.post("/reservas/{id_reserva}/recusar")
def recusar(request: Request, id_reserva: int, db: Session = Depends(get_db), usuario=Depends(require_user)):
    reserva, erro = _carregar(db, id_reserva)
    if erro:
        return erro
    try:
        reserva_service.recusar(db, reserva, usuario)
    except ErroValidacao as exc:
        return voltar_para("/painel", str(exc), "erro")
    auditoria_service.registrar(db, usuario.id_usuario, "RECUSA_RESERVA", f"Reserva #{id_reserva} recusada", obter_ip(request))
    return voltar_para("/painel", "Solicitação recusada.")


@router.post("/reservas/{id_reserva}/cancelar")
def cancelar(request: Request, id_reserva: int, db: Session = Depends(get_db), usuario=Depends(require_user)):
    reserva, erro = _carregar(db, id_reserva)
    if erro:
        return erro
    try:
        reserva_service.cancelar(db, reserva, usuario)
    except ErroValidacao as exc:
        return voltar_para("/painel", str(exc), "erro")
    auditoria_service.registrar(db, usuario.id_usuario, "CANCELAMENTO_RESERVA", f"Reserva #{id_reserva} cancelada", obter_ip(request))
    return voltar_para("/painel", "Reserva cancelada.")


@router.post("/reservas/{id_reserva}/retirada")
def retirada(request: Request, id_reserva: int, db: Session = Depends(get_db), usuario=Depends(require_user)):
    reserva, erro = _carregar(db, id_reserva)
    if erro:
        return erro
    try:
        reserva_service.registrar_retirada(db, reserva, usuario)
    except ErroValidacao as exc:
        return voltar_para("/painel", str(exc), "erro")
    auditoria_service.registrar(db, usuario.id_usuario, "RETIRADA", f"Retirada registrada na reserva #{id_reserva}", obter_ip(request))
    return voltar_para("/painel", "Retirada registrada. Bom trabalho!")


@router.post("/reservas/{id_reserva}/devolver")
def devolver(request: Request, id_reserva: int, db: Session = Depends(get_db), usuario=Depends(require_user)):
    reserva, erro = _carregar(db, id_reserva)
    if erro:
        return erro
    atraso = 0
    try:
        reserva_service.registrar_devolucao(db, reserva, usuario)
    except ErroValidacao as exc:
        return voltar_para("/painel", str(exc), "erro")

    from datetime import date

    atraso = max(0, (date.today() - reserva.data_prevista_fim).days)
    auditoria_service.registrar(
        db, usuario.id_usuario, "DEVOLUCAO",
        f"Reserva #{id_reserva} concluída (atraso de {atraso} dia(s))", obter_ip(request),
    )
    aviso = " Devolução registrada." if atraso == 0 else f" Devolução registrada com {atraso} dia(s) de atraso - taxa informativa gerada."
    return voltar_para("/painel", "Locação concluída." + aviso)


@router.post("/reservas/{id_reserva}/avaliar")
def avaliar(
    request: Request,
    id_reserva: int,
    nota: int = Form(5),
    comentario: str = Form(""),
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    reserva, erro = _carregar(db, id_reserva)
    if erro:
        return erro
    try:
        moderacao_service.avaliar(db, reserva, usuario.id_usuario, nota, comentario)
    except ErroValidacao as exc:
        return voltar_para("/painel", str(exc), "erro")
    auditoria_service.registrar(db, usuario.id_usuario, "AVALIACAO", f"Avaliação na reserva #{id_reserva} (nota {nota})", obter_ip(request))
    return voltar_para("/painel", "Avaliação registrada. Obrigado por contribuir com a comunidade!")


@router.get("/denunciar")
def tela_denunciar(
    request: Request,
    ferramenta: int = 0,
    usuario_id: int = 0,
    avaliacao: int = 0,
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    if usuario.is_admin:
        return voltar_para("/admin", "Contas administrativas usam a moderação do painel.", "erro")

    try:
        contexto = moderacao_service.contexto_denuncia(
            db, usuario.id_usuario, ferramenta=ferramenta, usuario_id=usuario_id, avaliacao=avaliacao
        )
    except ErroValidacao as exc:
        return voltar_para("/", str(exc), "erro")

    return render(
        request,
        "denunciar.html",
        usuario,
        motivos_denuncia=moderacao_service.MOTIVOS_DENUNCIA,
        **contexto,
    )


@router.post("/denuncias")
def denunciar(
    request: Request,
    motivo: str = Form(""),
    descricao: str = Form(""),
    id_denunciado: int = Form(0),
    id_ferramenta: int = Form(0),
    id_avaliacao: int = Form(0),
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    destino = f"/ferramentas/{id_ferramenta}#avaliacoes" if id_ferramenta else "/"
    if usuario.is_admin:
        return voltar_para(destino, "Contas administrativas usam o painel de moderação.", "erro")
    try:
        denuncia = moderacao_service.denunciar(
            db, usuario.id_usuario, motivo, descricao,
            id_denunciado=id_denunciado or None, id_ferramenta=id_ferramenta or None,
            id_avaliacao=id_avaliacao or None,
        )
    except ErroValidacao as exc:
        return voltar_para(destino, str(exc), "erro")

    auditoria_service.registrar(
        db, usuario.id_usuario, "DENUNCIA",
        f"Denúncia #{denuncia.id_denuncia} registrada (motivo: {denuncia.motivo}; "
        f"anúncio #{id_ferramenta or '-'}; avaliação #{id_avaliacao or '-'}; "
        f"usuário #{denuncia.id_denunciado or '-'})",
        obter_ip(request),
    )
    return voltar_para(
        destino,
        "Denúncia enviada para a moderação. Você será informado sobre a análise.",
    )


@router.get("/chat")
def chat(request: Request, reserva: int = 0, db: Session = Depends(get_db), usuario=Depends(require_user)):
    if usuario.is_admin:
        return voltar_para("/admin", "Contas administrativas não participam do chat entre vizinhos.", "erro")
    conversas = reserva_service.conversas(db, usuario)
    selecionada = None
    if reserva:
        try:
            candidata = reserva_service.obter(db, reserva)
        except ErroValidacao:
            candidata = None
        if candidata and usuario.id_usuario in (candidata.id_locador, candidata.id_locatario):
            if not reserva_service.pode_conversar(candidata):
                return voltar_para("/chat", "O chat é liberado depois que o locador aprovar a reserva.", "aviso")
            selecionada = candidata
    return render(request, "chat.html", usuario, conversas=conversas, selecionada=selecionada)


@router.post("/chat/{id_reserva}/mensagem")
def enviar_mensagem(
    request: Request,
    id_reserva: int,
    conteudo: str = Form(""),
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    reserva, erro = _carregar(db, id_reserva)
    if erro:
        return erro
    try:
        reserva_service.enviar_mensagem(db, reserva, usuario, conteudo)
    except ErroValidacao as exc:
        return voltar_para(f"/chat?reserva={id_reserva}", str(exc), "erro")
    return voltar_para(f"/chat?reserva={id_reserva}")
