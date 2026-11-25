"""Rotas de catálogo, anúncio, detalhe da ferramenta e painel do usuário."""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from src.controllers._utils import render, voltar_para
from src.middlewares.auth import obter_ip, require_user, usuario_atual
from src.services import auditoria_service, ferramenta_service, moderacao_service, reserva_service, usuario_service
from src.services.usuario_service import ErroValidacao

router = APIRouter(tags=["ferramentas"])


def _inteiro(valor: str) -> Optional[int]:
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        return None
    return numero if numero > 0 else None


def _decimal(valor: str) -> Optional[float]:
    try:
        numero = float(str(valor).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None
    return numero if numero > 0 else None


@router.get("/")
def catalogo(
    request: Request,
    q: str = "",
    categoria: str = "",
    estado: str = "",
    voltagem: str = "",
    distancia: str = "",
    db: Session = Depends(get_db),
    usuario=Depends(usuario_atual),
):
    # Os filtros chegam como texto do formulario: um valor invalido ou vazio
    # (ex.: "Todas as categorias") apenas desliga o filtro, sem gerar erro 422.
    id_categoria = _inteiro(categoria)

    tem_localizacao = bool(usuario and usuario.latitude is not None and usuario.longitude is not None)
    if "distancia" in request.query_params:
        # O usuario escolheu explicitamente no seletor (inclusive "Qualquer distância").
        distancia_maxima = _decimal(distancia)
    else:
        # Primeira visita: aplica o raio padrao em volta da localizacao do usuario.
        distancia_maxima = ferramenta_service.RAIO_PADRAO_KM if tem_localizacao else None

    ferramentas = ferramenta_service.buscar_catalogo(
        db,
        termo=q,
        id_categoria=id_categoria,
        estado=estado,
        voltagem=voltagem,
        usuario=usuario,
        distancia_maxima=distancia_maxima,
    )
    return render(
        request,
        "index.html",
        usuario,
        ferramentas=ferramentas,
        categorias=ferramenta_service.listar_categorias(db),
        estados=ferramenta_service.ESTADOS_CONSERVACAO,
        voltagens=ferramenta_service.VOLTAGENS,
        filtros={
            "q": q,
            "categoria": id_categoria,
            "estado": estado,
            "voltagem": voltagem,
            "distancia": distancia_maxima,
        },
        total=len(ferramentas),
        tem_localizacao=tem_localizacao,
    )


@router.get("/ferramentas/nova")
def tela_nova_ferramenta(request: Request, db: Session = Depends(get_db), usuario=Depends(require_user)):
    if usuario.is_admin:
        return voltar_para("/admin", "Contas administrativas não publicam anúncios.", "erro")
    return render(
        request,
        "nova_ferramenta.html",
        usuario,
        categorias=ferramenta_service.listar_categorias(db),
        estados=ferramenta_service.ESTADOS_CONSERVACAO,
        voltagens=ferramenta_service.VOLTAGENS,
    )


@router.post("/ferramentas/nova")
def publicar_ferramenta(
    request: Request,
    titulo: str = Form(""),
    descricao: str = Form(""),
    id_categoria: int = Form(0),
    estado_conservacao: str = Form(""),
    voltagem: str = Form(""),
    preco_diaria: str = Form(""),
    fotos: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    if usuario.is_admin:
        return voltar_para("/admin", "Contas administrativas não publicam anúncios.", "erro")

    try:
        ferramenta = ferramenta_service.criar_ferramenta(
            db, usuario, titulo, descricao, id_categoria, estado_conservacao, voltagem, preco_diaria, fotos
        )
    except ErroValidacao as exc:
        return render(
            request,
            "nova_ferramenta.html",
            usuario,
            erro=str(exc),
            categorias=ferramenta_service.listar_categorias(db),
            estados=ferramenta_service.ESTADOS_CONSERVACAO,
            voltagens=ferramenta_service.VOLTAGENS,
            form={"titulo": titulo, "descricao": descricao, "id_categoria": id_categoria,
                  "estado_conservacao": estado_conservacao, "preco_diaria": preco_diaria},
        )

    auditoria_service.registrar(
        db, usuario.id_usuario, "CRIACAO_ANUNCIO", f"Ferramenta #{ferramenta.id_ferramenta} - {ferramenta.titulo}", obter_ip(request)
    )
    return voltar_para(f"/ferramentas/{ferramenta.id_ferramenta}", "Anúncio publicado com sucesso!")


@router.get("/ferramentas/{id_ferramenta}")
def detalhe_ferramenta(
    request: Request,
    id_ferramenta: int,
    db: Session = Depends(get_db),
    usuario=Depends(usuario_atual),
):
    ferramenta = ferramenta_service.obter(db, id_ferramenta)
    eh_proprietario = bool(usuario and usuario.id_usuario == ferramenta.id_locador) if ferramenta else False
    eh_admin = bool(usuario and usuario.is_admin)

    # Anuncios excluidos ou suspensos so permanecem visiveis para o dono e para a administracao.
    if not ferramenta or (not ferramenta.publica and not eh_proprietario and not eh_admin):
        return voltar_para("/", "Este anúncio não está mais disponível.", "erro")

    nota, total_avaliacoes = ferramenta_service.media_avaliacoes(db, ferramenta.id_locador)
    avaliacoes = ferramenta_service.avaliacoes_recebidas(db, ferramenta.id_locador)

    return render(
        request,
        "detalhe_ferramenta.html",
        usuario,
        ferramenta=ferramenta,
        nota=nota,
        total_avaliacoes=total_avaliacoes,
        avaliacoes=avaliacoes,
        eh_proprietario=eh_proprietario,
        motivos_denuncia=moderacao_service.MOTIVOS_DENUNCIA,
        fotos=[f for f in [ferramenta.foto1, ferramenta.foto2, ferramenta.foto3, ferramenta.foto4, ferramenta.foto5] if f],
    )


@router.post("/ferramentas/{id_ferramenta}/excluir")
def excluir_ferramenta(
    request: Request,
    id_ferramenta: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    ferramenta = ferramenta_service.obter(db, id_ferramenta)
    if not ferramenta or ferramenta.id_locador != usuario.id_usuario or ferramenta.excluida:
        return voltar_para("/painel?aba=anuncios", "Anúncio não encontrado.", "erro")
    try:
        ferramenta_service.excluir_ferramenta(db, ferramenta, usuario)
    except ErroValidacao as exc:
        return voltar_para("/painel?aba=anuncios", str(exc), "erro")

    auditoria_service.registrar(
        db, usuario.id_usuario, "EXCLUSAO_ANUNCIO",
        f"Ferramenta #{id_ferramenta} - {ferramenta.titulo} removida (soft delete)", obter_ip(request),
    )
    return voltar_para("/painel?aba=anuncios", "Anúncio excluído. O histórico de locações foi preservado.")


@router.post("/ferramentas/{id_ferramenta}/disponibilidade")
def alterar_disponibilidade(
    request: Request,
    id_ferramenta: int,
    ativo: str = Form("1"),
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    ferramenta = ferramenta_service.obter(db, id_ferramenta)
    if not ferramenta or ferramenta.id_locador != usuario.id_usuario:
        return voltar_para("/painel?aba=anuncios", "Anúncio não encontrado.", "erro")
    try:
        ferramenta_service.alternar_disponibilidade(db, ferramenta, ativo == "1")
    except ErroValidacao as exc:
        return voltar_para("/painel?aba=anuncios", str(exc), "erro")

    auditoria_service.registrar(
        db, usuario.id_usuario, "ALTERACAO_STATUS_FERRAMENTA",
        f"Ferramenta #{ferramenta.id_ferramenta} -> {ferramenta.status_ferramenta}", obter_ip(request),
    )
    return voltar_para("/painel?aba=anuncios", "Status do anúncio atualizado.")


@router.get("/painel")
def painel(
    request: Request,
    aba: str = "reservas",
    db: Session = Depends(get_db),
    usuario=Depends(require_user),
):
    if usuario.is_admin:
        return voltar_para("/admin", "", "sucesso")

    reservas = reserva_service.listar_do_usuario(db, usuario)
    anuncios = ferramenta_service.listar_do_locador(db, usuario)
    resumo = reserva_service.resumo_financeiro(db, usuario)

    return render(
        request,
        "painel.html",
        usuario,
        reservas=reservas,
        anuncios=anuncios,
        resumo=resumo,
        aba=aba,
        pendentes=[r for r in reservas if r.id_locador == usuario.id_usuario and r.status_reserva == "pendente"],
    )


@router.get("/como-funciona")
def como_funciona(request: Request, usuario=Depends(usuario_atual)):
    return render(request, "como_funciona.html", usuario)


@router.get("/termo")
def termo_responsabilidade(request: Request, usuario=Depends(usuario_atual)):
    """Pagina publica com o texto integral do termo aceito no checkout."""
    return render(request, "termo.html", usuario, voltar_para_anuncio=request.query_params.get("ferramenta", ""))
