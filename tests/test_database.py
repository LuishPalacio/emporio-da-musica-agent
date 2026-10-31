"""Testes da camada de dados contra um MySQL real.

Requer `docker compose up -d` rodando antes do pytest (ver README).
"""

from emporio_agent import database


def test_products_loaded_with_expected_count():
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM products")
            assert cur.fetchone()["n"] == 65
    finally:
        conn.close()


def test_orders_loaded_with_expected_count():
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM orders")
            assert cur.fetchone()["n"] == 20
    finally:
        conn.close()


def test_foreign_key_product_category_is_enforced():
    """O MySQL (InnoDB) deve rejeitar um category_id que não existe —
    essa é justamente a integridade que o SQLite não garante por
    padrão, e uma das razões para a migração (ver database.py)."""

    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO products
                       (product_id, price_brl, name, category_id, stock_quantity, status)
                       VALUES (999999, 1.0, 'produto invalido', 999999, 1, 'active')"""
                )
                conn.commit()
                raised = False
            except Exception:
                conn.rollback()
                raised = True
        assert raised, "era esperado que o MySQL rejeitasse uma category_id inexistente"
    finally:
        conn.close()


def test_promotions_active_flag_filters_correctly():
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM promotions WHERE is_active = 1")
            assert cur.fetchone()["n"] == 4
    finally:
        conn.close()


def test_specs_json_column_roundtrips():
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT specs_json FROM products WHERE product_id = 95")
            row = cur.fetchone()
            assert row is not None
            assert "Cedro" in str(row["specs_json"])
    finally:
        conn.close()
