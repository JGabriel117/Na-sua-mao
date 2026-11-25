"""Regras de negócio de usuários: validação cadastral, hash bcrypt e login."""

import re
from datetime import datetime
from typing import Optional

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.models.models import Usuario
from src.repositories import usuario_repository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class ErroValidacao(Exception):
    """Erro de regra de negócio exibido ao usuário final."""


def gerar_hash(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha_texto: str, senha_hash: str) -> bool:
    try:
        return pwd_context.verify(senha_texto, senha_hash)
    except Exception:
        return False


def limpar_documento(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def validar_cpf(cpf: str) -> bool:
    """Validação matematica dos digitos verificadores do CPF."""
    numeros = limpar_documento(cpf)
    if len(numeros) != 11 or len(set(numeros)) == 1:
        return False

    for tamanho in (9, 10):
        soma = sum(int(numeros[i]) * ((tamanho + 1) - i) for i in range(tamanho))
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(numeros[tamanho]):
            return False
    return True


def formatar_cpf(cpf: str) -> str:
    numeros = limpar_documento(cpf)
    if len(numeros) != 11:
        return cpf
    return f"{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}"


def validar_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", email or ""))


def buscar_por_email(db: Session, email: str) -> Optional[Usuario]:
    return usuario_repository.buscar_por_email(db, email)


def buscar_por_id(db: Session, id_usuario: int) -> Optional[Usuario]:
    return usuario_repository.buscar_por_id(db, id_usuario)


def listar_admins(db: Session):
    return usuario_repository.listar_admins(db)


def criar_usuario(
    db: Session,
    nome: str,
    email: str,
    cpf: str,
    senha: str,
    confirmacao: str,
    cep: str = "",
    is_admin: bool = False,
) -> Usuario:
    """Cria usuário comum ou administrador aplicando RN01 (unicidade)."""
    nome = (nome or "").strip()
    email = (email or "").strip().lower()
    cpf_limpo = limpar_documento(cpf)

    if len(nome) < 3:
        raise ErroValidacao("Informe o nome completo.")
    if not validar_email(email):
        raise ErroValidacao("Informe um e-mail válido.")
    if not validar_cpf(cpf):
        raise ErroValidacao("CPF inválido. Verifique os digitos informados.")
    if len(senha or "") < 6:
        raise ErroValidacao("A senha deve ter no mínimo 6 caracteres.")
    if senha != confirmacao:
        raise ErroValidacao("A confirmação de senha não confere.")

    if usuario_repository.email_em_uso(db, email):
        raise ErroValidacao("Já existe uma conta cadastrada com este e-mail.")
    if usuario_repository.cpf_em_uso(db, formatar_cpf(cpf_limpo)):
        raise ErroValidacao("Já existe uma conta cadastrada com este CPF.")

    usuario = Usuario(
        nome=nome,
        email=email,
        cpf=formatar_cpf(cpf_limpo),
        cep=re.sub(r"\D", "", cep or "") or None,
        senha=gerar_hash(senha),
        is_admin=is_admin,
        status_conta="ativa",
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def autenticar(db: Session, email: str, senha: str) -> Usuario:
    identificador = (email or "").strip()
    usuario = buscar_por_email(db, identificador)
    if not usuario and identificador:
        # Login alternativo pelo CPF (mesmo campo do formulario).
        digitos = limpar_documento(identificador)
        if len(digitos) == 11:
            usuario = usuario_repository.buscar_por_cpf(db, formatar_cpf(digitos))
    if not usuario or not verificar_senha(senha, usuario.senha):
        raise ErroValidacao("E-mail/CPF ou senha incorretos.")
    if usuario.status_conta != "ativa":
        raise ErroValidacao("Esta conta está bloqueada. Procure a administração.")
    return usuario


def criar_admin(db: Session, nome: str, email: str, cpf: str, senha: str) -> Usuario:
    return criar_usuario(db, nome, email, cpf, senha, senha, is_admin=True)


def _coordenada(valor: str, campo: str, limite: float) -> Optional[float]:
    texto = (valor or "").strip().replace(",", ".")
    if not texto:
        return None
    try:
        numero = float(texto)
    except ValueError as exc:
        raise ErroValidacao(f"Informe um valor numérico para {campo}.") from exc
    if abs(numero) > limite:
        raise ErroValidacao(f"O valor de {campo} esta fora do intervalo permitido.")
    return numero


def atualizar_perfil(db: Session, usuario: Usuario, nome: str, email: str, cep: str = "") -> Usuario:
    """Atualiza os dados editaveis do perfil. CPF e imutavel (RN01).

    A localizacao NAO e editada aqui: ela vem do navegador ou do CEP
    (ver `definir_localizacao`), entao o usuario nunca digita coordenadas.
    """
    nome = (nome or "").strip()
    email = (email or "").strip().lower()

    if len(nome) < 3:
        raise ErroValidacao("Informe o nome completo.")
    if not validar_email(email):
        raise ErroValidacao("Informe um e-mail válido.")

    em_uso = usuario_repository.email_em_uso(db, email, ignorar_id=usuario.id_usuario)
    if em_uso:
        raise ErroValidacao("Este e-mail já esta em uso por outra conta.")

    usuario.nome = nome
    usuario.email = email
    usuario.cep = re.sub(r"\D", "", cep or "") or None

    db.commit()
    db.refresh(usuario)
    return usuario


def limpar_localizacao(db: Session, usuario: Usuario) -> Usuario:
    usuario.latitude = None
    usuario.longitude = None
    usuario.origem_localizacao = None
    usuario.localizacao_atualizada_em = None
    db.commit()
    db.refresh(usuario)
    return usuario


def definir_localizacao(db: Session, usuario: Usuario, latitude, longitude, origem: str) -> Usuario:
    """Grava coordenadas capturadas pelo navegador (origem='navegador') ou pelo CEP ('cep')."""
    lat = _coordenada(str(latitude), "latitude", 90)
    lon = _coordenada(str(longitude), "longitude", 180)
    if lat is None or lon is None:
        raise ErroValidacao("Coordenadas incompletas. Informe latitude e longitude.")

    usuario.latitude = lat
    usuario.longitude = lon
    usuario.origem_localizacao = origem
    usuario.localizacao_atualizada_em = datetime.utcnow()
    db.commit()
    db.refresh(usuario)
    return usuario


def alterar_senha(db: Session, usuario: Usuario, senha_atual: str, nova: str, confirmacao: str) -> Usuario:
    if not verificar_senha(senha_atual or "", usuario.senha):
        raise ErroValidacao("A senha atual informada esta incorreta.")
    _validar_nova_senha(usuario, nova, confirmacao)

    usuario.senha = gerar_hash(nova)
    db.commit()
    db.refresh(usuario)
    return usuario


def _validar_nova_senha(usuario: Usuario, nova: str, confirmacao: str) -> None:
    if len(nova or "") < 6:
        raise ErroValidacao("A nova senha deve ter no mínimo 6 caracteres.")
    if nova != confirmacao:
        raise ErroValidacao("A confirmação da nova senha não confere.")
    if verificar_senha(nova, usuario.senha):
        raise ErroValidacao("A nova senha deve ser diferente da senha atual.")


def recuperar_senha(db: Session, email: str, cpf: str, nova: str, confirmacao: str) -> Usuario:
    """Fluxo alternativo para quem não lembra a senha atual.

    A identidade é confirmada pela combinação e-mail + CPF cadastrados. Em um
    ambiente com serviço de e-mail, este passo seria substituído por um token
    de uso único enviado ao endereço da conta.
    """
    email = (email or "").strip().lower()
    if not validar_email(email):
        raise ErroValidacao("Informe o e-mail cadastrado na conta.")
    if not validar_cpf(cpf):
        raise ErroValidacao("Informe um CPF válido.")

    usuario = usuario_repository.buscar_por_email(db, email)
    if not usuario or limpar_documento(usuario.cpf) != limpar_documento(cpf):
        raise ErroValidacao("Os dados informados não conferem com nenhuma conta.")
    if usuario.status_conta != "ativa":
        raise ErroValidacao("Esta conta está bloqueada. Procure a administração.")

    _validar_nova_senha(usuario, nova, confirmacao)
    usuario.senha = gerar_hash(nova)
    db.commit()
    db.refresh(usuario)
    return usuario


def estatisticas_usuario(db: Session, usuario: Usuario) -> dict:
    """Numeros exibidos no topo da tela de perfil."""
    from src.repositories import ferramenta_repository, reserva_repository

    anuncios = ferramenta_repository.contar_do_locador(db, usuario.id_usuario)
    reservas = reserva_repository.contar_do_usuario(db, usuario.id_usuario)
    concluidas = reserva_repository.contar_do_usuario(db, usuario.id_usuario, status="concluida")
    notas = ferramenta_repository.avaliacoes_recebidas(db, usuario.id_usuario)
    media = round(sum(a.nota for a in notas) / len(notas), 1) if notas else None

    return {
        "anuncios": anuncios,
        "reservas": reservas,
        "concluidas": concluidas,
        "media": media,
        "total_avaliacoes": len(notas),
    }
