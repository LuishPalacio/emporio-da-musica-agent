# Exemplo 5 (não-trivial) — Produto esgotado, alternativa e política de parcelamento

Este é o cenário "não-trivial" do desafio: combina **consulta de dado em tempo real** (estoque
zerado de um produto específico, checado no MySQL) **e aplicação de regra de política**
(parcelamento), numa conversa de dois turnos que também demonstra a **persistência de sessão**
(no segundo turno, o agente já sabe do que se trata sem o cliente repetir o contexto).

O produto perguntado (`Giannini GF-3D Dreadnought Sunburst`, id 96) tem `stock_quantity = 0` no
catálogo — não é um produto inventado para o teste, é um dado real do `products.csv` fornecido.
O agente:
1. Confirma que o produto existe no catálogo, mas está sem estoque (não inventa disponibilidade).
2. Busca e sugere alternativas disponíveis de verdade (chamando `search_products` de novo).
3. No segundo turno, aplica corretamente a faixa de parcelamento certa (4x–6x sem juros, parcela
   mínima R$ 80 — diferente da faixa de 7x–12x, que tem mínimo de R$ 100) pro produto alternativo
   escolhido.
4. **Não finge poder fechar a venda** — isso não estava nos cenários sugeridos, mas apareceu
   durante os testes: numa primeira versão do prompt, o agente se ofereceu para "gerar o pedido e
   enviar o link de pagamento", uma ação que ele não tem ferramenta nenhuma para executar. Foi
   corrigido adicionando ao system prompt uma seção explícita listando o que o agente NÃO pode
   fazer (ver README, seção "Estratégia de prompt"). A resposta abaixo já reflete a correção.

Gerado com: `python -m emporio_agent.cli --session ex-estoque-parcelamento --message "..."` (dois
turnos na mesma sessão).
Modelo: `openai/gpt-oss-120b` via Groq.

---

**Cliente:** Vocês tem o violão Giannini GF-3D Dreadnought Sunburst?

**Sol:** Oi! O Giannini GF-3D Dreadnought Sunburst está no nosso catálogo, mas no momento está **sem estoque**.

Como alternativa, temos alguns dreadnoughts em Sunburst que já estão disponíveis:

- **Shelby SGD-195E Elétrico Aço Sunburst** – R$ 799,00 (com captação e afinador integrado) – 6 unidades em estoque.
- **Tagima Woodstock Dreadnought Natural** – R$ 899,00 – 11 unidades em estoque (acabamento natural, mas som semelhante).

Se quiser reservar o Giannini ou conferir outras opções, pode passar aqui na loja (Rua 14 de Maio, 3200 – Centro) ou chamar no WhatsApp (67) 3341-4444. Qualquer coisa, é só me falar! 🎸

**Cliente:** Gostei do Shelby SGD-195E. Posso parcelar em 6x sem juros?

**Sol:** Sim! O Shelby SGD-195E pode ser parcelado em **até 6x sem juros**, com parcela mínima de R$ 80,00.

Se quiser fechar a compra, pode vir à loja ou concluir online — lá você escolhe o cartão e o número de parcelas. Qualquer dúvida, só chamar! 🎸
