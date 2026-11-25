"""Utilitarios compartilhados de renderizacao (Jinja2) e formatacao."""

from decimal import Decimal
from datetime import datetime
from urllib.parse import quote

from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

ROTULOS_STATUS = {
    "pendente": "Aguardando aprovação",
    "aprovada": "Aguardando retirada",
    "em_uso": "Em uso",
    "concluida": "Concluída",
    "recusada": "Recusada",
    "cancelada": "Cancelada",
}

ROTULOS_STATUS_FERRAMENTA = {
    "disponivel": "Disponível",
    "indisponivel": "Indisponível",
    "suspensa": "Suspensa pela moderação",
    "excluida": "Excluída",
}

ROTULOS_DENUNCIA = {
    "aberta": "Em análise",
    "procedente": "Aprovada",
    "improcedente": "Rejeitada",
    "encerrada": "Encerrada",
}

CLASSES_BADGE_DENUNCIA = {
    "aberta": "bg-amber-100 text-amber-800",
    "procedente": "bg-red-100 text-red-700",
    "improcedente": "bg-gray-100 text-gray-500",
    "encerrada": "bg-gray-100 text-gray-500",
}

CLASSES_BADGE = {
    "pendente": "bg-amber-100 text-amber-800",
    "aprovada": "bg-amber-100 text-amber-800",
    "em_uso": "bg-emerald-100 text-emerald-700",
    "concluida": "bg-gray-100 text-gray-500",
    "recusada": "bg-red-50 text-red-600",
    "cancelada": "bg-gray-100 text-gray-500",
}


def brl(valor) -> str:
    try:
        numero = Decimal(str(valor or 0))
    except Exception:
        numero = Decimal("0")
    texto = f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def data_br(valor) -> str:
    if not valor:
        return "-"
    try:
        return valor.strftime("%d/%m/%Y")
    except AttributeError:
        return str(valor)


def cep_br(valor) -> str:
    digitos = "".join(c for c in str(valor or "") if c.isdigit())
    if len(digitos) != 8:
        return valor or "-"
    return f"{digitos[:5]}-{digitos[5:]}"


def data_hora_br(valor) -> str:
    if not valor:
        return "-"
    try:
        return valor.strftime("%d/%m/%Y %H:%M")
    except AttributeError:
        return str(valor)


def estrelas(nota) -> str:
    """Representacao textual de 1 a 5 estrelas (para leitores de tela)."""
    try:
        valor = max(0, min(5, int(nota)))
    except (TypeError, ValueError):
        valor = 0
    return "★" * valor + "☆" * (5 - valor)


def tempo_relativo(valor) -> str:
    """Data amigavel: hoje/ontem ou dd/mm/aaaa."""
    if not valor:
        return "-"
    try:
        dias = (datetime.utcnow().date() - valor.date()).days
    except AttributeError:
        return str(valor)
    if dias <= 0:
        return "hoje"
    if dias == 1:
        return "ontem"
    return valor.strftime("%d/%m/%Y")


templates.env.filters["brl"] = brl
templates.env.filters["data_br"] = data_br
templates.env.filters["cep_br"] = cep_br
templates.env.filters["data_hora_br"] = data_hora_br
templates.env.filters["estrelas"] = estrelas
templates.env.filters["tempo_relativo"] = tempo_relativo
templates.env.globals["ROTULOS_STATUS"] = ROTULOS_STATUS
templates.env.globals["ROTULOS_STATUS_FERRAMENTA"] = ROTULOS_STATUS_FERRAMENTA
templates.env.globals["ROTULOS_DENUNCIA"] = ROTULOS_DENUNCIA
templates.env.globals["CLASSES_BADGE_DENUNCIA"] = CLASSES_BADGE_DENUNCIA
templates.env.globals["CLASSES_BADGE"] = CLASSES_BADGE


def render(request: Request, template: str, usuario=None, status_code: int = 200, mensagem=None, tipo=None, **contexto):
    """Renderiza o template injetando o contexto padrao e o flash message.

    O flash pode vir da query string (`?msg=&tipo=`) ou ser passado diretamente
    pelo controller (util em respostas de erro renderizadas sem redirect).
    """
    mensagem = mensagem or request.query_params.get("msg")
    tipo = tipo or request.query_params.get("tipo", "sucesso")
    if tipo not in ("sucesso", "erro", "aviso"):
        tipo = "sucesso"
    contexto.update(
        {
            "request": request,
            "usuario": usuario,
            "mensagem": mensagem,
            "tipo_mensagem": tipo,
        }
    )
    return templates.TemplateResponse(request, template, contexto, status_code=status_code)


def voltar_para(caminho: str, mensagem: str = "", tipo: str = "sucesso"):
    """RedirectResponse com mensagem de feedback via query string."""
    from fastapi.responses import RedirectResponse

    url = caminho
    if mensagem:
        separador = "&" if "?" in caminho else "?"
        url = f"{caminho}{separador}msg={quote(mensagem)}&tipo={tipo}"
    return RedirectResponse(url=url, status_code=303)
