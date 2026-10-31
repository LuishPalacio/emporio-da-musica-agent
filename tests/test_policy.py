"""Testes do retrieval lexical sobre o manual de políticas.

O caso mais importante aqui é o de "me arrependi" -> seção de Direito
de Arrependimento: foi um bug real encontrado durante o
desenvolvimento (comparação de palavras exata não batia
"arrependi" / consulta com "arrependimento" / manual), corrigido com
normalização de acento + stemming por prefixo em policy._tokenize.
Esse teste existe para não deixar a regressão voltar.
"""

from emporio_agent import policy


def _headings(query: str, top_k: int = 2) -> list[str]:
    return [s.heading for s in policy.retrieve_relevant_sections(query, top_k=top_k)]


def test_arrependimento_encontra_secao_certa():
    headings = _headings("me arrependi da compra, quero devolver")
    assert headings[0] == "4.1 Direito de Arrependimento (Compras Online)"


def test_parcelamento():
    headings = _headings("posso parcelar em 10x")
    assert "3.1 Regras de Parcelamento" in headings


def test_escopo_acessorios():
    headings = _headings("voces vendem cordas de violao")
    assert headings[0] == "1. Sobre a Empório da Música"


def test_frete_outras_cidades():
    headings = _headings("quanto tempo demora o frete pra outra cidade")
    assert any("Frete" in h or "Outras Cidades" in h for h in headings)


def test_defeito_de_fabricacao():
    headings = _headings("o instrumento veio com defeito, posso trocar")
    assert any("Defeito" in h for h in headings)


def test_query_vazia_nao_quebra():
    assert policy.retrieve_relevant_sections("") == []


def test_query_sem_match_nao_quebra():
    assert policy.retrieve_relevant_sections("xablau blerg fooza") == []


def test_full_policy_text_contem_todas_as_secoes_principais():
    text = policy.load_full_policy_text()
    for trecho in [
        "Horário de Funcionamento",
        "Formas de Pagamento",
        "Trocas e Devoluções",
        "Frete e Entregas",
        "Garantia",
        "Privacidade e Proteção de Dados",
    ]:
        assert trecho in text
