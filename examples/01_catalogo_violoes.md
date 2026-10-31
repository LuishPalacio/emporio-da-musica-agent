# Exemplo 1 — Consulta de catálogo com filtro de preço

Cenário sugerido pelo desafio: "Quais opções de violões disponíveis custando até R$1000?" —
demonstra a ferramenta `search_products` (categoria + preço máximo).

Reparem que o modelo recebeu 13 violões ≤ R$1000 da ferramenta (ela não filtra estoque por
padrão), mas **excluiu sozinho** o "Giannini GF-3D Dreadnought Sunburst" da lista final — porque
o campo `in_stock: false` dele vinha no resultado da ferramenta, e o system prompt instrui a
nunca apresentar como disponível algo que não foi checado como tal.

Gerado com: `python -m emporio_agent.cli --session ex-catalogo --message "..."`
Modelo: `openai/gpt-oss-120b` via Groq.

---

**Cliente:** Quais opções de violões vocês têm disponíveis custando até R$1000?

**Sol:** Oi! Tudo bem? 😊

Segue a lista de violões que temos em estoque e que custam até **R$ 1.000**:

| Modelo | Tipo | Preço |
|--------|------|-------|
| **Tagima Memphis AC-39** – clássico nylon | Nylon | **R$ 429,90** |
| **Rozini RC-104** – clássico nylon | Nylon | **R$ 459,90** |
| **Shelby SN-100** – folk aço preto | Aço | **R$ 549,00** |
| **Giannini GF-1R** – folk sunburst | Aço | **R$ 579,90** |
| **Yamaha C40** – clássico nylon | Nylon | **R$ 599,90** |
| **Giannini GN-15** – clássico cedro | Nylon | **R$ 689,00** |
| **Yamaha F310** – folk aço | Aço | **R$ 699,90** |
| **Tagima Dallas Tuner** – folk aço | Aço | **R$ 749,00** |
| **Shelby SGD-195E** – eletroacústico | Aço + eletrônica | **R$ 799,00** |
| **Yamaha C70** – clássico nylon (intermediário) | Nylon | **R$ 849,00** |
| **Tagima Woodstock Dreadnought** – folk aço | Aço | **R$ 899,00** |
| **Tagima TW-7** – 7 cordas aço | Aço | **R$ 999,00** |

Todos estão disponíveis em estoque. Se quiser saber mais detalhes de algum modelo (especificações, cores, etc.) ou ver opções de pagamento e entrega, é só me falar! 🎸

Qual deles chamou mais a sua atenção?
