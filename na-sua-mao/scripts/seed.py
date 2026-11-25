import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from PIL import Image, ImageDraw  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import Base, SessionLocal, engine  # noqa: E402
from src.models.models import (  # noqa: E402
    Categoria,
    Ferramenta,
    Usuario,
)
from src.services.usuario_service import gerar_hash  # noqa: E402

UPLOAD_DIR = os.path.join("static", "uploads")

CATEGORIAS = [
    ("Jardinagem", "Cortadores de grama, podadores e afins"),
    ("Construção", "Furadeiras, serras, betoneiras e afins"),
    ("Limpeza", "Lavadoras de alta pressão, aspiradores e afins"),
    ("Elétrica", "Ferramentas elétricas e de medição"),
    ("Automotiva", "Macacos, chaves de roda e equipamentos de oficina"),
    ("Outros", "Demais ferramentas de uso doméstico"),
]

FERRAMENTAS = [
    {
        "titulo": "Furadeira de Impacto",
        "categoria": "Construção",
        "descricao": "Ferramenta em perfeito estado. Motor de 650W, com controle de velocidade.\n\n"
        "Acessórios inclusos: acompanha maleta original, empunhadura auxiliar, chave do mandril "
        "e jogo de brocas para concreto e madeira.",
        "voltagem": "220V",
        "estado": "Usado - Excelente",
        "preco": "35.00",
        "cores": [(37, 99, 235), (30, 64, 175), (79, 70, 229), (2, 132, 199), (67, 56, 202)],
    },
]


def gerar_imagem(nome_arquivo: str, titulo: str, cor, variacao: int = 1) -> str:
    """Cria uma imagem de demonstracao com o nome da ferramenta."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    imagem = Image.new("RGB", (900, 600), (249, 250, 251))
    desenho = ImageDraw.Draw(imagem)
    desenho.rounded_rectangle((60, 60, 840, 540), radius=32, fill=(255, 255, 255), outline=(229, 231, 235), width=3)
    deslocamento = 18 * (variacao - 1)
    desenho.rounded_rectangle(
        (330 + deslocamento, 140 + deslocamento, 570 + deslocamento, 380 + deslocamento),
        radius=28,
        fill=cor,
    )
    desenho.rectangle((395 + deslocamento, 205 + deslocamento, 505 + deslocamento, 315 + deslocamento), fill=(255, 255, 255))
    desenho.text((360, 450), f"{titulo}  -  foto {variacao}", fill=(17, 24, 39))
    caminho = os.path.join(UPLOAD_DIR, nome_arquivo)
    imagem.save(caminho, format="JPEG", quality=88, optimize=True)
    return nome_arquivo


def executar() -> None:
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        for nome, descricao in CATEGORIAS:
            if not db.query(Categoria).filter(Categoria.nome == nome).first():
                db.add(Categoria(nome=nome, descricao=descricao))
        db.commit()

        admin = db.query(Usuario).filter(Usuario.email == "admin@email.com").first()
        if not admin:
            admin = Usuario(
                nome="Administração Na Sua Mão",
                email="admin@email.com",
                cpf="111.444.777-35",
                senha=gerar_hash("admin123"),
                is_admin=True,
                status_conta="ativa",
                latitude=-3.7319,
                longitude=-38.5267,
                origem_localizacao="cep",
                localizacao_atualizada_em=datetime.utcnow(),
            )
            db.add(admin)

        joao = db.query(Usuario).filter(Usuario.email == "joao@email.com").first()
        if not joao:
            joao = Usuario(
                nome="João Victor",
                email="joao@email.com",
                cpf="529.982.247-25",
                senha=gerar_hash("joao123" if False else "123456"),
                is_admin=False,
                status_conta="ativa",
                cep="60170000",
                latitude=-3.7350,
                longitude=-38.4980,
                origem_localizacao="cep",
                localizacao_atualizada_em=datetime.utcnow(),
            )
            db.add(joao)

        db.commit()
        db.refresh(joao)

        for indice, dados in enumerate(FERRAMENTAS, start=1):
            if db.query(Ferramenta).filter(Ferramenta.titulo == dados["titulo"]).first():
                continue
            categoria = db.query(Categoria).filter(Categoria.nome == dados["categoria"]).first()
            cores = dados["cores"]
            fotos = [
                gerar_imagem(f"seed-ferramenta-{indice}-{v}.jpg", dados["titulo"], cores[(v - 1) % len(cores)], v)
                for v in range(1, len(cores) + 1)
            ]
            db.add(
                Ferramenta(
                    id_locador=joao.id_usuario,
                    id_categoria=categoria.id_categoria,
                    titulo=dados["titulo"],
                    descricao=dados["descricao"],
                    voltagem=dados["voltagem"],
                    estado_conservacao=dados["estado"],
                    preco_diaria=Decimal(dados["preco"]),
                    status_ferramenta="disponivel",
                    foto1=fotos[0],
                    foto2=fotos[1] if len(fotos) > 1 else None,
                    foto3=fotos[2] if len(fotos) > 2 else None,
                    foto4=fotos[3] if len(fotos) > 3 else None,
                    foto5=fotos[4] if len(fotos) > 4 else None,
                )
            )
        db.commit()

        print("Seed concluído com sucesso.")
        print("  Administrador: admin@email.com / admin123")
        print("  Usuário João:  joao@email.com / 123456")
        print("  Anúncio:       Furadeira de Impacto (João)")
        print("Próximo passo:  python run.py")
    finally:
        db.close()


if __name__ == "__main__":
    executar()
