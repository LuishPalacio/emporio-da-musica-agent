"""Fixtures compartilhadas dos testes.

Os testes em test_database.py e test_tools.py precisam de um MySQL de
verdade no ar (suba com `docker compose up -d` antes de rodar
`pytest`) — não usamos mocks para essa camada porque o que mais
importa testar aqui são as queries SQL em si (joins, filtros, cálculo
de promoção), e um mock do banco não pegaria um erro de SQL. Os
testes em test_policy.py e test_formatting.py não precisam de banco.

Se o MySQL não estiver acessível, os testes que dependem dele falham
com uma mensagem clara (gerada em `database._connect_raw`) em vez de
travar esperando indefinidamente.
"""

from __future__ import annotations

import pytest

from emporio_agent import database


@pytest.fixture(scope="session", autouse=True)
def _rebuild_database_once():
    """Recria o schema/dados no início da sessão de testes, uma única vez.

    Garante que os testes rodem contra um estado conhecido (os CSVs em
    data/), independentemente do que ficou no banco de uma execução
    manual anterior do agente.
    """

    database.ensure_database(force_rebuild=True)
