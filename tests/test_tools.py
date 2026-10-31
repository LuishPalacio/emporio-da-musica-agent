"""Testes das ferramentas (function calling) contra o MySQL real.

Requer `docker compose up -d` rodando antes do pytest (ver README).
Os valores esperados aqui vêm diretamente dos CSVs em data/ — qualquer
mudança nos dados de origem deve atualizar estes testes também.
"""

from emporio_agent import tools


def test_search_products_by_category_and_max_price():
    result = tools.search_products(category="violões", max_price=1000)
    names = {p["name"] for p in result["products"]}
    assert "Tagima Memphis AC-39 Nylon Natural" in names
    # "Taylor 110e Dreadnought Natural" custa 5999 -> não deveria aparecer
    assert "Taylor 110e Dreadnought Natural" not in names
    # todos os resultados devem respeitar o teto de preço
    assert all(p["price_brl"] <= 1000 for p in result["products"])


def test_search_products_excludes_discontinued_by_default():
    result = tools.search_products(query="7 cordas")
    names = {p["name"] for p in result["products"]}
    # "Shelby SN-7C 7 Cordas Nylon Natural" (product_id 113) está
    # discontinued no CSV -- search_products só traz produtos 'active'
    assert "Shelby SN-7C 7 Cordas Nylon Natural" not in names


def test_get_product_details_by_name_single_match():
    result = tools.get_product_details("Takamine GD20")
    assert result["found"] is True
    assert len(result["matches"]) == 1
    product = result["matches"][0]
    assert product["product_id"] == 95
    assert product["price_formatted"] == "R$ 2.199,00"
    assert product["in_stock"] is True


def test_get_product_details_finds_discontinued_product():
    """get_product_details (diferente de search_products) deve achar
    produtos descontinuados, para o agente poder explicar a situação
    em vez de dizer que o produto não existe."""

    result = tools.get_product_details("Shelby SN-7C")
    assert result["found"] is True
    assert result["matches"][0]["status"] == "discontinued"


def test_get_product_details_not_found():
    result = tools.get_product_details("instrumento que nao existe xyz123")
    assert result["found"] is False


def test_get_product_details_by_id():
    result = tools.get_product_details("95")
    assert result["found"] is True
    assert result["matches"][0]["name"] == "Takamine GD20 Dreadnought Natural"


def test_active_promotions_apply_discount_correctly():
    result = tools.get_active_promotions()
    by_id = {p["product_id"]: p for p in result["promotions"]}
    # product_id 121: Ohana CK-20 Concert Natural, preço 549, desconto 20%
    assert 121 in by_id
    assert by_id[121]["price_with_promotion_formatted"] == "R$ 439,20"


def test_order_status_by_id():
    result = tools.get_order_status(order_id=1)
    assert result["found"] is True
    order = result["orders"][0]
    assert order["status"] == "delivered"
    assert order["total_formatted"] == "R$ 11.499,00"
    assert order["items"][0]["product_name"] == "Martin D-28 Dreadnought Natural"


def test_order_status_by_phone_returns_most_recent_first():
    # cliente 3 (Pedro Henrique Oliveira) tem os pedidos 1 (delivered)
    # e 19 (cancelled); por telefone deve vir o mais recente primeiro
    result = tools.get_order_status(phone="(67) 98432-1098")
    assert result["found"] is True
    order_ids = [o["order_id"] for o in result["orders"]]
    assert order_ids[0] == 19  # 2026-02-22, mais recente que o pedido 1 (2025-10-15)


def test_order_status_requires_identifier():
    result = tools.get_order_status()
    assert "error" in result


def test_order_status_not_found():
    result = tools.get_order_status(order_id=99999)
    assert result["found"] is False


def test_list_categories_matches_store_catalog():
    result = tools.list_categories()
    names = {c["name"] for c in result["categories"]}
    # as 9 categorias de categories.csv -- a loja vende só instrumentos.
    # Nota: "Cordas Orquestrais" (violinos, violas, violoncelos) é uma
    # categoria real de instrumentos, não um acessório -- por isso o
    # teste checa a lista exata em vez de uma heurística por palavra
    # como "nenhum nome contém 'corda'" (que daria falso positivo aqui).
    assert names == {
        "Guitarras",
        "Baixos",
        "Baterias e Percussão",
        "Teclados e Pianos",
        "Violões",
        "Instrumentos de Sopro (Madeiras)",
        "Instrumentos de Sopro (Metais)",
        "Cordas Orquestrais",
        "Ukuleles",
    }


def test_execute_tool_dispatch():
    result = tools.execute_tool("get_product_details", {"identifier": "95"})
    assert result["found"] is True


def test_execute_tool_unknown_tool():
    result = tools.execute_tool("ferramenta_que_nao_existe", {})
    assert "error" in result
