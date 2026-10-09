import sys
import os
import pytest
from unittest.mock import MagicMock


sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.services.avaliacao_service import validar_comentario, avaliar_experiencia, resolver_denuncia
from src.services.ferramenta_service import cadastrar_ferramenta, calcular_distancia

# TU01: Validação de palavras proibidas no comentário
def test_validar_comentario():
    comentario_valido = validar_comentario("Ótima ferramenta, me ajudou muito!")
    comentario_invalido = validar_comentario("Essa ferramenta é um lixo")
    
    assert comentario_valido is True
    assert comentario_invalido is False

# TU02: Bloqueio de avaliação para reserva não finalizada
def test_avaliar_experiencia_status_invalido():
    db_mock = MagicMock()
    reserva_mock = MagicMock()
    reserva_mock.status_reserva = "EM_USO"
    db_mock.query().filter().first.return_value = reserva_mock

    resultado = avaliar_experiencia(db_mock, reserva_id=1, avaliador_id=2, nota=5, comentario="Bom estado")
    
    assert "erro" in resultado
    assert "Somente aluguéis finalizados podem ser avaliados" in resultado["erro"]

# TU03: Cadastro bem-sucedido de ferramenta
def test_cadastrar_ferramenta_sucesso():
    db_mock = MagicMock()
    
    
    categoria_mock = MagicMock()
    categoria_mock.id_categoria = 1
    db_mock.query().filter().first.return_value = categoria_mock

    dados_ferramenta = {
        "nome": "Furadeira de Impacto",
        "descricao": "Teste",
        "categoria": "Construção",
        "valor_diaria": 45.0
    }

    resultado = cadastrar_ferramenta(db_mock, dados_ferramenta, locador_id=1)
    
    assert "ferramenta" in resultado
    assert resultado["ferramenta"].titulo == "Furadeira de Impacto"

# TU04: Cálculo de distância usando a fórmula de Haversine
def test_calcular_distancia_haversine():
    coord1 = (-15.7942, -47.8822)
    coord2 = (-15.8042, -47.8922)
    
    distancia = calcular_distancia(coord1, coord2)
    
    assert isinstance(distancia, float)
    assert distancia > 0.0

# TU05: Resolução de denúncia inexistente
def test_resolver_denuncia_nao_encontrada():
    db_mock = MagicMock()
    db_mock.query().filter().first.return_value = None

    resultado = resolver_denuncia(db_mock, denuncia_id=999, resolucao="Usuário advertido", admin_id=1)
    
    assert "erro" in resultado
    assert "Denúncia não encontrada" in resultado["erro"]