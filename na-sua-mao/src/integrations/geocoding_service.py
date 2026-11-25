"""Resolucao de CEP em coordenadas.

Usado como fallback quando o usuario nao autoriza a geolocalizacao do navegador:
o sistema localiza o CEP cadastrado e passa a calcular o raio de distancia a partir dele.

Fontes (nessa ordem):
1. BrasilAPI v2  -> ja devolve latitude/longitude do CEP;
2. Nominatim     -> geocodifica o endereco retornado pela BrasilAPI/ViaCEP.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Tuple

TIMEOUT_SEGUNDOS = 6
USER_AGENT = "NaSuaMao/1.0 (projeto academico)"
BRASILAPI_CEP = "https://brasilapi.com.br/api/cep/v2/{cep}"
NOMINATIM = "https://nominatim.openstreetmap.org/search"

MENSAGEM_FALHA = (
    "Não foi possível localizar este CEP agora. Verifique o CEP em Meu perfil "
    "ou informe latitude e longitude manualmente."
)


def limpar_cep(cep: str) -> str:
    return "".join(c for c in (cep or "") if c.isdigit())


def _buscar_json(url: str):
    requisicao = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def _consultar_brasilapi(cep: str):
    try:
        dados = _buscar_json(BRASILAPI_CEP.format(cep=cep))
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None
    if not dados or dados.get("errors"):
        return None
    return dados


def _geocodificar_endereco(dados: dict) -> Tuple[float, float, str] | None:
    partes = [
        dados.get("street"),
        dados.get("neighborhood"),
        dados.get("city"),
        dados.get("state"),
        "Brasil",
    ]
    consulta = ", ".join(p for p in partes if p)
    if not consulta:
        return None
    url = f"{NOMINATIM}?" + urllib.parse.urlencode({"q": consulta, "format": "json", "limit": 1})
    try:
        resultado = _buscar_json(url)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None
    if not resultado:
        return None
    rotulo = f"{dados.get('city') or ''}/{dados.get('state') or ''}".strip("/")
    return float(resultado[0]["lat"]), float(resultado[0]["lon"]), rotulo or consulta


def coordenadas_por_cep(cep: str) -> Tuple[float, float, str]:
    """Devolve (latitude, longitude, rotulo) do CEP.

    Levanta LookupError com mensagem pronta para o usuario quando nao for possivel.
    """
    digitos = limpar_cep(cep)
    if len(digitos) != 8:
        raise LookupError("CEP inválido. Informe os 8 digitos em Meu perfil.")

    dados = _consultar_brasilapi(digitos)
    if dados:
        coordenadas = ((dados.get("location") or {}).get("coordinates") or {})
        latitude = coordenadas.get("latitude")
        longitude = coordenadas.get("longitude")
        if latitude and longitude:
            rotulo = ", ".join(p for p in (dados.get("city"), dados.get("state")) if p)
            return float(latitude), float(longitude), rotulo or f"CEP {digitos}"

        refinado = _geocodificar_endereco(dados)
        if refinado:
            return refinado

    raise LookupError(MENSAGEM_FALHA)
