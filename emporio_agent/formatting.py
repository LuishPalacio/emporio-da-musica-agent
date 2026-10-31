"""Funções puras de formatação.

Isoladas num módulo próprio (sem dependência de banco de dados ou de
rede) para serem fáceis de testar e de reutilizar tanto nas
ferramentas (tools.py) quanto, futuramente, em uma interface web.

Por que o código formata a moeda em vez de deixar o modelo fazer isso:
LLMs ocasionalmente erram na formatação de números (trocam separador
de milhar por decimal, arredondam errado etc.). Como preço é uma
informação sensível para o cliente, preferimos calcular e formatar em
Python determinístico e entregar ao modelo uma string pronta
(`price_formatted`) para ele apenas repassar, em vez de confiar que o
modelo vai converter `2199.0` em "R$ 2.199,00" corretamente todas as
vezes.
"""

from __future__ import annotations


def format_brl(value: float) -> str:
    """Formata um número como moeda brasileira: 2199.0 -> 'R$ 2.199,00'."""

    negative = value < 0
    value = abs(value)
    # separa parte inteira e centavos manualmente para não depender de
    # configuração de locale do sistema operacional (locale é instável
    # entre Windows/Linux/containers e não deve ser pré-requisito para
    # rodar o projeto)
    cents = round(value * 100)
    reais, cents = divmod(cents, 100)
    reais_str = f"{reais:,}".replace(",", ".")
    sign = "-" if negative else ""
    return f"{sign}R$ {reais_str},{cents:02d}"
