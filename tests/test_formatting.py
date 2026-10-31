from emporio_agent.formatting import format_brl


def test_format_brl_simple():
    assert format_brl(2199.0) == "R$ 2.199,00"


def test_format_brl_no_cents_in_source():
    # price_brl no CSV às vezes vem sem casas decimais (ex.: "849"
    # em vez de "849.00") — o valor float resultante ainda deve
    # formatar com duas casas de centavos.
    assert format_brl(849.0) == "R$ 849,00"


def test_format_brl_rounds_cents():
    assert format_brl(439.195) == "R$ 439,20" or format_brl(439.195) == "R$ 439,19"


def test_format_brl_thousands_separator():
    assert format_brl(12500.0) == "R$ 12.500,00"


def test_format_brl_millions():
    assert format_brl(1234567.89) == "R$ 1.234.567,89"


def test_format_brl_zero():
    assert format_brl(0.0) == "R$ 0,00"


def test_format_brl_negative():
    assert format_brl(-50.0) == "-R$ 50,00"
