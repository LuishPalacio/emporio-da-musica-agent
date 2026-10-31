"""Configuração central do agente.

Mantém num só lugar os caminhos de arquivo e os parâmetros que variam
por ambiente (modelo, chave de API etc.), lidos de variáveis de
ambiente com valores padrão sensatos. Qualquer outro módulo que
precise de um caminho ou parâmetro de configuração importa daqui, em
vez de espalhar `os.environ.get(...)` pelo código.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega variáveis de um arquivo .env na raiz do projeto, se existir.
# Em produção (ex.: variável já exportada pelo sistema/container) isso
# é um no-op silencioso.
load_dotenv()

# --- Caminhos -----------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONVERSATIONS_DIR = PROJECT_ROOT / "conversations"

PRODUCTS_CSV = DATA_DIR / "products.csv"
CATEGORIES_CSV = DATA_DIR / "categories.csv"
CUSTOMERS_CSV = DATA_DIR / "customers.csv"
ORDERS_CSV = DATA_DIR / "orders.csv"
ORDER_ITEMS_CSV = DATA_DIR / "order_items.csv"
PROMOTIONS_CSV = DATA_DIR / "promotions.csv"
POLICY_MD = DATA_DIR / "politicas_da_loja.md"

# --- Banco de dados (MySQL) ----------------------------------------------
#
# Os valores padrão aqui casam com docker-compose.yml: rodando
# `docker compose up -d` com um `.env` vazio (ou copiado direto de
# .env.example sem editar essas linhas), o agente já conecta sem
# configuração extra. Em um ambiente diferente (CI, outro host, MySQL
# gerenciado na nuvem) basta sobrescrever essas variáveis de ambiente.

MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3307"))
MYSQL_USER = os.environ.get("MYSQL_USER", "emporio")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "emporio_dev_only")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "emporio_musica")

# --- Modelo / provedor ----------------------------------------------------

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Modelo padrão: um Claude Sonnet atual. É o ponto de equilíbrio entre
# qualidade de raciocínio (necessária para seguir várias regras de
# política ao mesmo tempo e decidir corretamente quando chamar cada
# ferramenta) e custo/latência para um caso de uso de atendimento ao
# cliente. Veja a justificativa completa no README.
MODEL_NAME = os.environ.get("EMPORIO_MODEL", "claude-sonnet-5")

MAX_TOKENS = int(os.environ.get("EMPORIO_MAX_TOKENS", "1024"))

# Quantos turnos (pares pergunta/resposta) de histórico são reenviados
# como contexto a cada chamada ao modelo. Evita que conversas muito
# longas estourem o contexto / custo sem necessidade.
MAX_HISTORY_TURNS = int(os.environ.get("EMPORIO_MAX_HISTORY_TURNS", "20"))
