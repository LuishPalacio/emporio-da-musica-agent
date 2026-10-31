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
#
# Provedor: Groq (https://console.groq.com), escolhido por ser gratuito
# (sem cartão de crédito, cota generosa no plano free) e por expor uma
# API compatível com o formato da OpenAI -- incluindo tool calling, o
# mecanismo central deste agente. Usamos o pacote `openai` apontando
# pra base_url da Groq em vez de um SDK próprio da Groq: é a forma
# oficialmente documentada de integrar, e evita mais uma dependência
# só pra isso. Justificativa completa (e as alternativas pagas/locais
# consideradas) está no README.

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Modelo padrão: openai/gpt-oss-120b, o modelo open-weight da OpenAI
# hospedado pela Groq com foco declarado em tool-calling confiável --
# exatamente a capacidade mais importante para este agente (decidir
# corretamente QUANDO chamar cada ferramenta, e com quais parâmetros).
# openai/gpt-oss-20b é a alternativa mais rápida/leve, caso a latência
# ou os limites de taxa do plano gratuito pesem mais que a qualidade
# de raciocínio em algum cenário de uso.
MODEL_NAME = os.environ.get("EMPORIO_MODEL", "openai/gpt-oss-120b")

MAX_TOKENS = int(os.environ.get("EMPORIO_MAX_TOKENS", "1024"))

# Quantos turnos (pares pergunta/resposta) de histórico são reenviados
# como contexto a cada chamada ao modelo. Evita que conversas muito
# longas estourem o contexto / custo sem necessidade.
MAX_HISTORY_TURNS = int(os.environ.get("EMPORIO_MAX_HISTORY_TURNS", "20"))
