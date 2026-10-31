# Exemplo 4 — Aplicação da política de devolução (direito de arrependimento)

Cenário sugerido pelo desafio: "Me arrependi da minha compra, posso devolver meu pedido?" —
demonstra a ferramenta `search_store_policies`. A pergunta do cliente usa o verbo "arrependi",
enquanto o manual usa o substantivo "Arrependimento" — esse par é justamente o que motivou o
stemming em `policy.py` (ver `tests/test_policy.py::test_arrependimento_encontra_secao_certa`):
sem ele, a busca lexical não encontrava a seção certa.

Gerado com: `python -m emporio_agent.cli --session ex-devolucao --message "..."`
Modelo: `openai/gpt-oss-120b` via Groq.

---

**Cliente:** Comprei um violão pela internet semana passada e me arrependi, posso devolver?

**Sol:** Oi! Tudo bem? Entendo a situação. 😉

**Devolução de compras online**
- Você tem até **7 dias corridos** após receber o violão para solicitar a devolução, sem precisar justificar.
- O instrumento precisa estar na embalagem original, sem sinais de uso, com todos os acessórios e manuais.
- O reembolso será feito na mesma forma de pagamento em até **10 dias úteis**.
- O frete de devolução corre por conta da **loja** quando o motivo for arrependimento.

Para avançarmos, preciso confirmar alguns dados:

1. Número do pedido (ou o e-mail usado na compra)
2. Telefone cadastrado no pedido

Com essas informações, nossa equipe consegue abrir a solicitação de devolução e orientar o envio do produto. Se preferir, você também pode falar diretamente com a gente pelo WhatsApp (67) 3341-4444 ou ir à loja física.

Qualquer dúvida, é só chamar! 🎸
