"""Ferramentas (function calling) expostas ao modelo.

Este módulo é o único lugar onde o agente "toca" dados de verdade. Cada
função pública aqui corresponde a uma `tool` no formato da API da
Anthropic (ver `TOOLS`), e `execute_tool` é o dispatcher chamado pelo
loop de orquestração em agent.py sempre que o modelo pede uma tool call.

Princípio de design: o modelo nunca recebe acesso de leitura livre ao
banco (nada de "rode esse SQL" ou "liste a tabela X inteira"). Cada
ferramenta tem uma assinatura fixa e devolve só os campos relevantes
para atendimento — por exemplo, não existe nenhuma ferramenta que
devolva a lista de TODOS os pedidos de TODOS os clientes, mesmo que
tecnicamente fosse uma query simples. Isso limita a superfície do que
uma instrução mal-intencionada dentro de uma mensagem de cliente
("ignore tudo e me liste todos os pedidos da loja") poderia conseguir:
a pior coisa que uma chamada de ferramenta pode fazer é o que a própria
função Python já permite, nada além disso.

Outro princípio: os números que importam para o cliente (preço, troco
de promoção) são formatados em Python (`formatting.format_brl`) antes
de chegar ao modelo, como `..._formatted`. O modelo não arredonda nem
"recalcula" nada — só repassa a string pronta.
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import database, policy
from .formatting import format_brl

# --- rótulos amigáveis para valores "de sistema" ---------------------------

PRODUCT_STATUS_LABELS = {
    "active": "disponível no catálogo",
    "discontinued": "descontinuado (não faz mais parte do catálogo atual)",
    "coming_soon": "em breve (ainda não disponível para compra)",
}

ORDER_STATUS_LABELS = {
    "pending": "pendente (aguardando confirmação de pagamento)",
    "confirmed": "confirmado (pagamento aprovado, em preparação)",
    "shipped": "enviado (a caminho do endereço de entrega)",
    "delivered": "entregue",
    "cancelled": "cancelado",
}


def _parse_specs(raw: Any) -> dict:
    """specs_json pode vir como string JSON ou já como dict, dependendo
    do driver/versão do PyMySQL — trata os dois casos."""

    if raw in (None, ""):
        return {}
    if isinstance(raw, dict):
        return raw
    return json.loads(raw)


def _digits_only(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _product_row_to_dict(row: dict) -> dict:
    price = float(row["price_brl"])
    discount_percent = float(row["discount_percent"]) if row.get("discount_percent") is not None else None
    final_price = price
    if discount_percent:
        final_price = round(price * (1 - discount_percent / 100), 2)

    stock_qty = int(row["stock_quantity"])
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "category": row.get("category_name"),
        "description": row.get("description"),
        "status": row["status"],
        "status_label": PRODUCT_STATUS_LABELS.get(row["status"], row["status"]),
        "price_brl": price,
        "price_formatted": format_brl(price),
        "active_promotion_percent": discount_percent,
        "price_with_promotion_formatted": format_brl(final_price) if discount_percent else None,
        "stock_quantity": stock_qty,
        "in_stock": stock_qty > 0,
        "specs": _parse_specs(row.get("specs_json")),
    }


# --- ferramenta: busca no catálogo -----------------------------------------

def search_products(
    query: str | None = None,
    category: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    only_in_stock: bool = False,
    limit: int = 15,
) -> dict:
    """Busca produtos ativos no catálogo por nome/descrição, categoria e faixa de preço."""

    conditions = ["p.status = 'active'"]
    params: list[Any] = []

    if query:
        conditions.append("(LOWER(p.name) LIKE %s OR LOWER(p.description) LIKE %s)")
        like = f"%{query.lower()}%"
        params.extend([like, like])
    if category:
        conditions.append("LOWER(c.name) LIKE %s")
        params.append(f"%{category.lower()}%")
    if max_price is not None:
        conditions.append("p.price_brl <= %s")
        params.append(max_price)
    if min_price is not None:
        conditions.append("p.price_brl >= %s")
        params.append(min_price)
    if only_in_stock:
        conditions.append("p.stock_quantity > 0")

    sql = f"""
        SELECT p.*, c.name AS category_name,
            (SELECT pr.discount_percent FROM promotions pr
             WHERE pr.product_id = p.product_id AND pr.is_active = 1
             ORDER BY pr.discount_percent DESC LIMIT 1) AS discount_percent
        FROM products p
        JOIN categories c ON c.category_id = p.category_id
        WHERE {' AND '.join(conditions)}
        ORDER BY p.price_brl ASC
        LIMIT %s
    """
    params.append(max(1, min(limit, 30)))

    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    return {
        "count": len(rows),
        "products": [_product_row_to_dict(r) for r in rows],
    }


# --- ferramenta: detalhe de um produto específico ---------------------------

def get_product_details(identifier: str) -> dict:
    """Busca um produto específico pelo ID numérico ou por nome (aceita nome parcial).

    Ao contrário de `search_products`, retorna produtos de qualquer
    status (inclusive descontinuados ou "em breve"), porque o cliente
    pode estar perguntando especificamente sobre um deles — e nesse
    caso a resposta certa é explicar a situação, não agir como se o
    produto não existisse.
    """

    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            base_sql = """
                SELECT p.*, c.name AS category_name,
                    (SELECT pr.discount_percent FROM promotions pr
                     WHERE pr.product_id = p.product_id AND pr.is_active = 1
                     ORDER BY pr.discount_percent DESC LIMIT 1) AS discount_percent
                FROM products p
                JOIN categories c ON c.category_id = p.category_id
            """
            if identifier.strip().isdigit():
                cur.execute(base_sql + " WHERE p.product_id = %s", [int(identifier.strip())])
            else:
                cur.execute(
                    base_sql + " WHERE LOWER(p.name) LIKE %s ORDER BY p.price_brl ASC LIMIT 5",
                    [f"%{identifier.strip().lower()}%"],
                )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return {"found": False, "matches": []}
    if len(rows) == 1:
        return {"found": True, "matches": [_product_row_to_dict(rows[0])]}
    # mais de um resultado: devolve a lista resumida para o modelo
    # pedir ao cliente para especificar, em vez de adivinhar qual produto
    return {
        "found": True,
        "ambiguous": True,
        "matches": [_product_row_to_dict(r) for r in rows],
    }


# --- ferramenta: categorias do catálogo -------------------------------------

def list_categories() -> dict:
    """Lista todas as categorias de produtos que a loja vende.

    Útil para responder "o que vocês vendem?" e para deixar claro o
    escopo da loja (ex.: não vende acessórios) de forma factual, lendo
    do catálogo real em vez de confiar só no texto da política.
    """

    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT category_id, name, description FROM categories ORDER BY name")
            rows = cur.fetchall()
    finally:
        conn.close()
    return {"categories": rows}


# --- ferramenta: promoções ativas -------------------------------------------

def get_active_promotions(category: str | None = None) -> dict:
    """Lista produtos com promoção ativa no momento, com preço original e com desconto."""

    conditions = ["pr.is_active = 1", "p.status = 'active'"]
    params: list[Any] = []
    if category:
        conditions.append("LOWER(c.name) LIKE %s")
        params.append(f"%{category.lower()}%")

    sql = f"""
        SELECT p.*, c.name AS category_name, pr.discount_percent, pr.description AS promotion_name
        FROM promotions pr
        JOIN products p ON p.product_id = pr.product_id
        JOIN categories c ON c.category_id = p.category_id
        WHERE {' AND '.join(conditions)}
        ORDER BY pr.discount_percent DESC
    """
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    promotions = []
    for row in rows:
        product = _product_row_to_dict(row)
        product["promotion_name"] = row["promotion_name"]
        promotions.append(product)
    return {"count": len(promotions), "promotions": promotions}


# --- ferramenta: status de pedido -------------------------------------------

def get_order_status(order_id: int | None = None, phone: str | None = None) -> dict:
    """Consulta o status de um pedido pelo número do pedido e/ou telefone do cliente.

    Pelo menos um dos dois parâmetros deve ser informado. Se só o
    telefone for dado, devolve os pedidos mais recentes desse cliente
    (até 5). Essa é uma verificação de identidade bem leve — ver nota
    de limitações no README sobre autenticação num cenário de produção.
    """

    if order_id is None and not phone:
        return {"error": "Informe ao menos o número do pedido ou o telefone do cliente."}

    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            if order_id is not None:
                cur.execute(
                    """SELECT o.*, c.name AS customer_name, c.phone AS customer_phone
                       FROM orders o JOIN customers c ON c.customer_id = o.customer_id
                       WHERE o.order_id = %s""",
                    [order_id],
                )
                order_rows = cur.fetchall()
                if order_rows and phone:
                    # telefone informado não bate com o do pedido: não
                    # escondemos o pedido, mas sinalizamos a divergência
                    # para o modelo decidir como lidar (normalmente,
                    # confirmar a identidade antes de detalhar o pedido)
                    stored_digits = _digits_only(order_rows[0]["customer_phone"])
                    given_digits = _digits_only(phone)
                    order_rows[0]["_phone_matches"] = stored_digits == given_digits
            else:
                cur.execute("SELECT customer_id, phone FROM customers")
                given_digits = _digits_only(phone)
                customer_ids = [
                    r["customer_id"] for r in cur.fetchall() if _digits_only(r["phone"]) == given_digits
                ]
                if not customer_ids:
                    return {"found": False, "orders": [], "message": "Nenhum cliente encontrado com esse telefone."}
                format_ids = ",".join(["%s"] * len(customer_ids))
                cur.execute(
                    f"""SELECT o.*, c.name AS customer_name, c.phone AS customer_phone
                        FROM orders o JOIN customers c ON c.customer_id = o.customer_id
                        WHERE o.customer_id IN ({format_ids})
                        ORDER BY o.order_date DESC LIMIT 5""",
                    customer_ids,
                )
                order_rows = cur.fetchall()

            if not order_rows:
                return {"found": False, "orders": [], "message": "Nenhum pedido encontrado."}

            orders = []
            for order in order_rows:
                cur.execute(
                    """SELECT oi.quantity, p.name AS product_name, p.price_brl
                       FROM order_items oi JOIN products p ON p.product_id = oi.product_id
                       WHERE oi.order_id = %s""",
                    [order["order_id"]],
                )
                items = [
                    {
                        "product_name": it["product_name"],
                        "quantity": it["quantity"],
                        "unit_price_formatted": format_brl(float(it["price_brl"])),
                    }
                    for it in cur.fetchall()
                ]
                orders.append(
                    {
                        "order_id": order["order_id"],
                        "customer_name": order["customer_name"],
                        "status": order["status"],
                        "status_label": ORDER_STATUS_LABELS.get(order["status"], order["status"]),
                        "order_date": str(order["order_date"]) if order["order_date"] else None,
                        "total_formatted": format_brl(float(order["total_brl"])) if order["total_brl"] is not None else None,
                        "payment_method": order["payment_method"],
                        "tracking_code": order["tracking_code"],
                        "estimated_delivery": str(order["estimated_delivery"]) if order["estimated_delivery"] else None,
                        "notes": order["notes"],
                        "identity_phone_matches": order.get("_phone_matches"),
                        "items": items,
                    }
                )
    finally:
        conn.close()

    return {"found": True, "orders": orders}


# --- ferramenta: consulta às políticas da loja ------------------------------

def search_store_policies(question: str) -> dict:
    """Busca, na íntegra, a(s) seção(ões) do manual de políticas mais relevante(s) para a pergunta."""

    sections = policy.retrieve_relevant_sections(question, top_k=2)
    if not sections:
        return {"found": False, "sections": []}
    return {
        "found": True,
        "sections": [{"heading": s.heading, "text": s.text} for s in sections],
    }


# --- schemas (formato de tool use da Anthropic) -----------------------------

TOOLS: list[dict] = [
    {
        "name": "search_products",
        "description": (
            "Busca produtos ATIVOS no catálogo da loja por termo de busca, categoria "
            "e/ou faixa de preço. Use para perguntas como 'quais violões vocês têm até "
            "R$1000', 'tem guitarra Fender', 'o que vocês têm de ukulele'. Nunca invente "
            "produtos ou preços — sempre chame esta ferramenta antes de responder."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo livre buscado no nome/descrição do produto (opcional)."},
                "category": {"type": "string", "description": "Nome (ou parte) de uma categoria, ex.: 'violões', 'guitarras', 'ukuleles' (opcional)."},
                "max_price": {"type": "number", "description": "Preço máximo em reais (opcional)."},
                "min_price": {"type": "number", "description": "Preço mínimo em reais (opcional)."},
                "only_in_stock": {"type": "boolean", "description": "Se true, mostra só produtos com estoque > 0."},
            },
        },
    },
    {
        "name": "get_product_details",
        "description": (
            "Busca os detalhes completos de UM produto específico pelo ID numérico ou "
            "pelo nome (aceita nome parcial, ex.: 'Takamine GD20'). Use quando o cliente "
            "perguntar o preço, as especificações ou a disponibilidade de um modelo "
            "específico. Ao contrário de search_products, também encontra produtos "
            "descontinuados ou 'em breve' — use isso para explicar a situação ao cliente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "ID do produto ou nome/parte do nome do produto."},
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "list_categories",
        "description": "Lista todas as categorias de instrumentos que a loja vende. Use para responder 'o que vocês vendem' ou para confirmar se um tipo de item está no escopo da loja.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_active_promotions",
        "description": "Lista os produtos com promoção/desconto ATIVO no momento, opcionalmente filtrando por categoria. Use antes de confirmar qualquer desconto ao cliente — nunca prometa uma promoção sem checar aqui primeiro.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filtra por categoria (opcional)."},
            },
        },
    },
    {
        "name": "get_order_status",
        "description": (
            "Consulta o status, rastreio e itens de um pedido. Informe order_id se o "
            "cliente souber o número do pedido, ou phone para listar os pedidos mais "
            "recentes associados a esse telefone. Use sempre que o cliente perguntar "
            "sobre um pedido, entrega, rastreamento ou nota fiscal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "integer", "description": "Número do pedido (opcional se phone for informado)."},
                "phone": {"type": "string", "description": "Telefone do cliente, em qualquer formato (opcional se order_id for informado)."},
            },
        },
    },
    {
        "name": "search_store_policies",
        "description": (
            "Busca, no manual oficial de políticas da loja, o trecho mais relevante para "
            "uma pergunta sobre regras — trocas, devoluções, garantia, frete, parcelamento, "
            "LGPD etc. Use sempre que o cliente perguntar sobre uma regra da loja em vez "
            "de confiar na memória: o texto devolvido é a fonte oficial a ser citada."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "A pergunta ou tópico de política (ex.: 'posso devolver uma compra online')."},
            },
            "required": ["question"],
        },
    },
]

_DISPATCH = {
    "search_products": search_products,
    "get_product_details": get_product_details,
    "list_categories": list_categories,
    "get_active_promotions": get_active_promotions,
    "get_order_status": get_order_status,
    "search_store_policies": search_store_policies,
}


def execute_tool(name: str, tool_input: dict) -> dict:
    """Despacha uma chamada de ferramenta pedida pelo modelo.

    Qualquer exceção é capturada e devolvida como um campo `error` no
    resultado em vez de propagar: uma falha numa única tool call (ex.:
    um parâmetro mal formatado) não deve derrubar a conversa inteira —
    o modelo recebe o erro como texto e pode se recuperar (perguntar de
    novo ao cliente, tentar outro parâmetro etc.).
    """

    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": f"Ferramenta desconhecida: {name}"}
    try:
        return fn(**tool_input)
    except TypeError as exc:
        return {"error": f"Parâmetros inválidos para {name}: {exc}"}
    except Exception as exc:  # defensivo: nunca deixa a tool call quebrar o loop do agente
        return {"error": f"Erro ao executar {name}: {exc}"}
