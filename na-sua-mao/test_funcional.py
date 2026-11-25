from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from src.services import ferramenta_service, moderacao_service
from src.models.models import Reserva

client = TestClient(app)

# ==========================================
# 1. TESTES UNITÁRIOS (Camada de Serviços)
# ==========================================

def test_validar_comentario():
    # TU01: Validação de comentário (bloqueia termos impróprios ou textos curtos)
    assert moderacao_service.validar_comentario("muito bom recomendo") is True
    assert moderacao_service.validar_comentario("ruim") is False  # Demasiado curto
    assert moderacao_service.validar_comentario("produto lixo e péssimo") is False  # Termo proibido


def test_avaliar_experiencia_status_invalido():
    # TU02: Impedir avaliação de reservas ativas (só em estado concluído)
    db = SessionLocal()
    try:
        reserva_ativa = Reserva(status_reserva="em_uso")
        with pytest.raises(Exception):
            moderacao_service.avaliar(db, reserva_ativa, 1, 5, "ótimo atendimento aqui")
    finally:
        db.close()


def test_cadastrar_ferramenta_sucesso():
    # TU03: Validação e conversão do preço da diária da ferramenta
    preco = ferramenta_service._converter_preco("45,00")
    assert preco == Decimal("45.00")


def test_calcular_distancia_haversine():
    # TU04: Cálculo geodésico da distância entre coordenadas (Haversine)
    dist = ferramenta_service.calcular_distancia(-3.7319, -38.5267, -3.7420, -38.5100)
    assert isinstance(dist, float)
    assert dist > 0.0


def test_resolver_denuncia_nao_encontrada():
    # TU05: Tratamento de erro ao tentar moderar denúncia inexistente
    db = SessionLocal()
    try:
        with pytest.raises(Exception):
            moderacao_service.encerrar_denuncia(db, id_denuncia=99999)
    finally:
        db.close()


# ==========================================
# 2. TESTES DE INTEGRAÇÃO (Rotas / API)
# ==========================================

def test_health_check_endpoint():
    # TI01: Verifica a saúde e disponibilidade da aplicação ASGI
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "Na Sua Mao"}


def test_catalogo_publico_acesso():
    # TI02: Valida se o catálogo de ferramentas responde corretamente ao utilizador
    response = client.get("/")
    assert response.status_code == 200
    assert "Na sua mão" in response.text


def test_login_credenciais_invalidas():
    # TI03: Submissão de credenciais incorretas no formulário de autenticação
    response = client.post("/login", data={"email": "inexistente@teste.com", "senha": "errada"})
    assert response.status_code in [200, 303]


def test_detalhe_ferramenta_inexistente():
    # TI04: Acesso a um anúncio de ferramenta com ID que não existe na base de dados
    response = client.get("/ferramentas/999999")
    assert response.status_code in [200, 303] # Redireciona com mensagem de erro tratada