"""Servico de midias: aceita PNG, JPEG, JPG e WEBP e comprime para <= 500 KB (RNF02)."""

import io
import os
import uuid
from typing import Optional

from PIL import Image, UnidentifiedImageError

UPLOAD_DIR = os.path.join("static", "uploads")
LIMITE_BYTES = 500 * 1024
MAX_DIMENSAO = 1600
EXTENSOES_PERMITIDAS = {"png", "jpg", "jpeg", "webp"}


def _garantir_diretorio() -> None:
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def _extensao(nome: str) -> str:
    return (os.path.splitext(nome or "")[1] or "").replace(".", "").lower()


def _comprimir(imagem: Image.Image) -> bytes:
    """Reduz dimensao e qualidade até o arquivo ficar abaixo de 500 KB."""
    imagem = imagem.convert("RGB")
    largura, altura = imagem.size
    escala = min(1.0, MAX_DIMENSAO / max(largura, altura))
    if escala < 1.0:
        imagem = imagem.resize((int(largura * escala), int(altura * escala)))

    for dimensao in (MAX_DIMENSAO, 1200, 900, 700, 500):
        atual = imagem.copy()
        atual.thumbnail((dimensao, dimensao))
        for qualidade in (88, 80, 72, 64, 55, 45, 35):
            buffer = io.BytesIO()
            atual.save(buffer, format="JPEG", quality=qualidade, optimize=True)
            if buffer.tell() <= LIMITE_BYTES:
                return buffer.getvalue()

    buffer = io.BytesIO()
    atual.save(buffer, format="JPEG", quality=25, optimize=True)
    return buffer.getvalue()


def salvar_imagem(arquivo) -> Optional[str]:
    """Persiste a imagem em static/uploads e devolve apenas o nome do arquivo."""
    if arquivo is None or not getattr(arquivo, "filename", ""):
        return None

    extensao = _extensao(arquivo.filename)
    if extensao not in EXTENSOES_PERMITIDAS:
        raise ValueError("Formato inválido. Envie PNG, JPEG, JPG ou WEBP.")

    dados = arquivo.file.read()
    if not dados:
        return None

    try:
        with Image.open(io.BytesIO(dados)) as original:
            original.load()
            conteudo = _comprimir(original)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Não foi possível ler a imagem enviada.") from exc

    _garantir_diretorio()
    nome = f"{uuid.uuid4().hex}.jpg"
    with open(os.path.join(UPLOAD_DIR, nome), "wb") as destino:
        destino.write(conteudo)
    return nome


def remover_imagem(nome: Optional[str]) -> None:
    if not nome:
        return
    caminho = os.path.join(UPLOAD_DIR, os.path.basename(nome))
    if os.path.exists(caminho):
        os.remove(caminho)
