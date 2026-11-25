# Na sua mão

Plataforma web para compartilhamento e locação de ferramentas entre vizinhos, desenvolvida com **FastAPI**, **SQLAlchemy**, **Jinja2**, **Tailwind CSS** e **MySQL 8.0**.

## Funcionalidades principais

* **Contas e autenticação:** Cadastro de usuários (com validação de CPF, e-mail, senha e aceite LGPD), login por e-mail ou CPF via cookie `HttpOnly` (JWT), troca de senha e recuperação de senha por e-mail + CPF.
* **Catálogo e busca:** Busca por palavra-chave, categoria, estado de conservação, voltagem e distância máxima (calculada por Haversine a partir da localização do navegador ou estimada pelo CEP via BrasilAPI v2 / Nominatim).
* **Anúncios de ferramentas:** Publicação com até 5 fotos (comprimidas automaticamente para até 500 KB em JPEG), controle de disponibilidade e exclusão lógica (*soft delete*) preservando o histórico de reservas.
* **Reservas, contrato e chat:** Solicitação com cálculo automático de diárias, aceite do Termo de Responsabilidade e Isenção de Segurança, geração de contrato com hash SHA-256, prevenção de conflito de agenda sem expor datas ocupadas, registro de retirada e devolução (com taxa informativa de atraso de 50% da diária por dia excedente) e chat liberado após aprovação.
* **Avaliações, denúncias e administração:** Avaliação após conclusão da locação, denúncias de anúncios, usuários ou avaliações, filtro de termos ofensivos/tamanho mínimo, painel administrativo com moderação, suspensão/reativação de contas, cadastro de administradores e log de auditoria.

## Estrutura do projeto

* `main.py` e `run.py` — Inicialização da aplicação FastAPI e execução do servidor.
* `database.py` — Configuração da conexão com o banco de dados e sessão SQLAlchemy.
* `scripts/init_db.py` e `scripts/seed.py` — Inicialização do schema e carga de dados iniciais.
* `src/controllers/` — Rotas e controllers web (`auth_controller.py`, `ferramenta_controller.py`, `reserva_controller.py`, `perfil_controller.py`, `admin_controller.py`, `_utils.py`).
* `src/services/` — Regras de negócio (`usuario_service.py`, `ferramenta_service.py`, `reserva_service.py`, `moderacao_service.py`, `auditoria_service.py`).
* `src/repositories/` — Consultas ao banco via ORM.
* `src/models/models.py` — Modelos ORM das 11 tabelas da aplicação.
* `src/middlewares/auth.py` — Autenticação por token/cookie, verificação de perfil/admin e captura de IP.
* `src/integrations/` — Geocodificação por CEP (`geocoding_service.py`) e processamento/compressão de imagens (`storage_service.py`).
* `templates/` e `static/` — Templates HTML/Jinja2, scripts (`carrossel.js`, `geo_auto.js`) e arquivos estáticos/uploads.
* `test_funcional.py` — Suíte de testes funcionais.

## Como executar o projeto
   
   pip install -r requirements.txt\
   python scripts/init_db.py\
   python scripts/seed.py\
   python run.py\
   http://localhost:8000

## Como executar os testes funcionais
   
   python test_funcional.py

## Conta admin

   Usuário: Admin@email.com\
   Senha: admin123
