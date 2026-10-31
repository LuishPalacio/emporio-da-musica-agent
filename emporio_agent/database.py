"""Camada de dados: carrega os CSVs da loja num banco MySQL.

Por que um banco relacional (e não listas de dicionários em memória
nem um DataFrame pandas): os dados da Empório da Música são
relacionais por natureza — pedidos referenciam clientes e produtos,
itens de pedido referenciam pedidos e produtos, promoções referenciam
produtos. SQL resolve filtros e joins desse tipo de forma direta e
testável, sem reimplementar lógica de junção manualmente em Python.

Por que MySQL especificamente (rodando via Docker Compose, ver
docker-compose.yml na raiz do projeto) em vez de SQLite: é a opção
mais "parecida com produção" para esse tipo de aplicação — um banco
cliente-servidor de verdade, com um motor (InnoDB) que impõe
integridade referencial (uma FOREIGN KEY inválida falha de verdade,
em vez de passar batido como aconteceria no SQLite sem
`PRAGMA foreign_keys=ON`) e tipos de dado mais adequados a dinheiro
(DECIMAL em vez de float) e a dados semiestruturados (coluna JSON
nativa para os specs dos produtos). O preço disso é precisar de um
servidor rodando — por isso o projeto inclui um `docker-compose.yml`
que sobe tudo com um único comando, para não exigir que quem for
avaliar o repositório instale MySQL manualmente.

Importante (e isso não muda com a troca de SQLite para MySQL): o LLM
NUNCA escreve ou executa SQL diretamente. As ferramentas em tools.py
expõem um conjunto fixo de funções Python com parâmetros tipados, e
são essas funções — não o modelo — que montam as queries SQL (sempre
parametrizadas, nunca por concatenação de string). Isso é uma escolha
deliberada de arquitetura: um agente "text-to-SQL" livre é mais
flexível, mas também mais difícil de auditar e mais arriscado
(consultas inesperadas, custosas, ou que vazam colunas que não
deveriam ser expostas ao cliente). Com funções fixas, cada ferramenta
tem um contrato claro do que pode e não pode consultar.

O banco é reconstruído a partir dos CSVs toda vez que o processo sobe
(ver `ensure_database`), porque os CSVs são a fonte de verdade neste
protótipo. Em um sistema real seria o contrário: o banco (ou a API do
e-commerce) seria a fonte de verdade, e os CSVs nem existiriam.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import pymysql
import pymysql.cursors

from . import config

# Ordem importa: tabelas "pai" primeiro (para CREATE TABLE ... FOREIGN
# KEY funcionar) e tabelas "filhas" primeiro na hora de limpar (DROP),
# já que não desligamos a checagem de foreign keys do MySQL — preferimos
# deixar o banco nos avisar se alguma ordem estiver errada.
_CREATE_STATEMENTS = [
    """
    CREATE TABLE categories (
        category_id INT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        description TEXT
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE customers (
        customer_id INT PRIMARY KEY,
        name VARCHAR(150) NOT NULL,
        phone VARCHAR(30),
        email VARCHAR(150),
        city VARCHAR(100)
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE products (
        product_id INT PRIMARY KEY,
        price_brl DECIMAL(10, 2) NOT NULL,
        name VARCHAR(200) NOT NULL,
        category_id INT,
        description TEXT,
        stock_quantity INT NOT NULL DEFAULT 0,
        status VARCHAR(20) NOT NULL,
        specs_json JSON,
        created_at DATE,
        FOREIGN KEY (category_id) REFERENCES categories(category_id)
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE orders (
        order_id INT PRIMARY KEY,
        customer_id INT,
        order_date DATE,
        status VARCHAR(20) NOT NULL,
        total_brl DECIMAL(10, 2),
        payment_method VARCHAR(30),
        tracking_code VARCHAR(20),
        estimated_delivery DATE,
        notes TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE order_items (
        order_id INT NOT NULL,
        quantity INT NOT NULL,
        product_id INT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE promotions (
        promotion_id INT PRIMARY KEY,
        product_id INT,
        discount_percent DECIMAL(5, 2) NOT NULL,
        description VARCHAR(200),
        is_active TINYINT(1) NOT NULL DEFAULT 0,
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    ) ENGINE=InnoDB
    """,
]

# Ordem inversa da criação, para respeitar as foreign keys ao limpar.
_DROP_ORDER = ["order_items", "promotions", "orders", "products", "customers", "categories"]


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _none_if_blank(value: str | None) -> str | None:
    return value if value not in (None, "") else None


def _connect_raw(*, with_database: bool, retries: int = 1, retry_delay: float = 2.0):
    """Abre uma conexão PyMySQL, tentando algumas vezes.

    O retry existe porque, logo depois de `docker compose up -d`, o
    container do MySQL ainda pode estar inicializando por alguns
    segundos — sem isso, a primeira tentativa de conexão do processo
    Python frequentemente chega antes do banco estar pronto para
    aceitar conexões.
    """

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return pymysql.connect(
                host=config.MYSQL_HOST,
                port=config.MYSQL_PORT,
                user=config.MYSQL_USER,
                password=config.MYSQL_PASSWORD,
                database=config.MYSQL_DATABASE if with_database else None,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
            )
        except pymysql.err.OperationalError as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_delay)
    raise ConnectionError(
        "Não foi possível conectar ao MySQL em "
        f"{config.MYSQL_HOST}:{config.MYSQL_PORT}. "
        "O banco está no ar? Rode `docker compose up -d` na raiz do "
        "projeto (ou ajuste MYSQL_HOST/MYSQL_PORT no .env se você "
        "estiver usando um MySQL próprio)."
    ) from last_error


def build_database() -> None:
    """(Re)constrói o schema e os dados a partir dos CSVs em data/.

    Idempotente: pode ser chamada toda vez que o processo sobe. Como o
    volume de dados é pequeno, recriar do zero é mais simples e mais
    seguro (garante que o banco nunca fica dessincronizado dos CSVs)
    do que tentar fazer um upsert incremental.
    """

    conn = _connect_raw(with_database=True, retries=15, retry_delay=2.0)
    try:
        with conn.cursor() as cur:
            for table in _DROP_ORDER:
                cur.execute(f"DROP TABLE IF EXISTS {table}")
            for statement in _CREATE_STATEMENTS:
                cur.execute(statement)

            categories = _read_csv(config.CATEGORIES_CSV)
            cur.executemany(
                "INSERT INTO categories (category_id, name, description) VALUES (%s, %s, %s)",
                [(int(r["category_id"]), r["name"], r.get("description")) for r in categories],
            )

            products = _read_csv(config.PRODUCTS_CSV)
            product_rows = []
            for row in products:
                specs = row.get("specs") or "{}"
                json.loads(specs)  # falha cedo se o specs do CSV não for JSON válido
                product_rows.append(
                    (
                        int(row["product_id"]),
                        float(row["price_brl"]),
                        row["name"],
                        int(row["category_id"]),
                        row.get("description"),
                        int(row["stock_quantity"]),
                        row["status"],
                        specs,
                        row.get("created_at") or None,
                    )
                )
            cur.executemany(
                """INSERT INTO products
                   (product_id, price_brl, name, category_id, description,
                    stock_quantity, status, specs_json, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                product_rows,
            )

            customers = _read_csv(config.CUSTOMERS_CSV)
            cur.executemany(
                """INSERT INTO customers (customer_id, name, phone, email, city)
                   VALUES (%s, %s, %s, %s, %s)""",
                [
                    (int(r["customer_id"]), r["name"], r.get("phone"), r.get("email"), r.get("city"))
                    for r in customers
                ],
            )

            orders = _read_csv(config.ORDERS_CSV)
            cur.executemany(
                """INSERT INTO orders
                   (order_id, customer_id, order_date, status, total_brl,
                    payment_method, tracking_code, estimated_delivery, notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        int(r["order_id"]),
                        int(r["customer_id"]),
                        r.get("order_date") or None,
                        r["status"],
                        float(r["total_brl"]) if r.get("total_brl") else None,
                        r.get("payment_method"),
                        _none_if_blank(r.get("tracking_code")),
                        _none_if_blank(r.get("estimated_delivery")),
                        _none_if_blank(r.get("notes")),
                    )
                    for r in orders
                ],
            )

            order_items = _read_csv(config.ORDER_ITEMS_CSV)
            cur.executemany(
                "INSERT INTO order_items (order_id, quantity, product_id) VALUES (%s, %s, %s)",
                [(int(r["order_id"]), int(r["quantity"]), int(r["product_id"])) for r in order_items],
            )

            promotions = _read_csv(config.PROMOTIONS_CSV)
            cur.executemany(
                """INSERT INTO promotions
                   (promotion_id, product_id, discount_percent, description, is_active)
                   VALUES (%s, %s, %s, %s, %s)""",
                [
                    (
                        int(r["promotion_id"]),
                        int(r["product_id"]),
                        float(r["discount_percent"]),
                        r.get("description"),
                        int(r["is_active"]),
                    )
                    for r in promotions
                ],
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_database_ready = False


def ensure_database(force_rebuild: bool = False) -> None:
    """Garante que o schema/dados existam, construindo-os se necessário.

    Usa uma flag em memória de processo para não reconstruir o banco a
    cada chamada de ferramenta dentro da mesma execução do agente —
    só na primeira vez (ou quando `force_rebuild=True`, usado pelos
    testes para garantir um estado limpo e conhecido).
    """

    global _database_ready
    if force_rebuild or not _database_ready:
        build_database()
        _database_ready = True


def get_connection() -> pymysql.connections.Connection:
    """Abre uma conexão com o banco, construindo-o antes se preciso.

    `cursorclass=DictCursor` (configurado em `_connect_raw`) permite
    acessar colunas por nome (`row["price_brl"]`) em vez de por índice
    posicional, deixando o código das ferramentas mais legível.
    """

    ensure_database()
    return _connect_raw(with_database=True, retries=5, retry_delay=1.0)
