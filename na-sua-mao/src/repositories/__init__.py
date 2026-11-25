"""Camada de acesso a dados: consultas SQLAlchemy reutilizáveis.

Os repositórios não contêm regra de negócio; apenas isolam as consultas ao
banco para que os Services permaneçam focados nas decisões do domínio.
"""
