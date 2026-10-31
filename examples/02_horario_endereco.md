# Exemplo 2 — Informações gerais da loja (e uma divergência real nos dados)

Cenário sugerido pelo desafio: "Qual o endereço da loja?" — testado junto com horário de
funcionamento, que é uma pergunta igualmente comum. Esses dados vêm direto do system prompt
(seção "Dados básicos da loja"), não exigem chamada de ferramenta — e o modelo ainda cruza o
horário de sábado com a data/hora atual injetada no prompt para avisar que a loja já fechou.

O segundo turno mostra algo que não estava nos cenários sugeridos, mas apareceu de verdade ao ler
com atenção o PDF fornecido: o manual de políticas cita **dois números de WhatsApp diferentes**
em seções diferentes (seção 1.2: (67) 3341-4444; seção 7: (67) 3321-4500). Em vez de simplesmente
ignorar ou "inventar" qual está certo, o agente foi instruído a sempre citar o da seção 1.2 como
oficial e reconhecer a divergência com transparência se o cliente perguntar — sem fingir que não
existe. Ver a seção "Nota de qualidade de dados" em `data/politicas_da_loja.md`.

Gerado com: `python -m emporio_agent.cli --session ex-info-loja --message "..."` (dois turnos na
mesma sessão, demonstrando também a persistência de conversa).
Modelo: `openai/gpt-oss-120b` via Groq.

---

**Cliente:** Qual o endereço da loja e o horário de funcionamento?

**Sol:** Oi! Tudo bem?

**Endereço:** Rua 14 de Maio, 3200 – Centro, Campo Grande – MS, CEP 79202-333
**Telefone/WhatsApp:** (67) 3341-4444

**Horário de funcionamento:**
- Segunda a sexta: 09:00 – 18:00
- Sábado: 09:00 – 13:00 (hoje, fechamos às 13h)
- Domingo e feriados: fechado

Qualquer outra dúvida, é só chamar! 🎸😊

**Cliente:** Vi um anúncio de vocês com o número (67) 3321-4500, é esse o whatsapp certo?

**Sol:** Entendo! Nosso material interno tem duas linhas de contato, mas o número oficial de WhatsApp da Empório da Música é **(67) 3341-4444**.

Se precisar, posso confirmar isso com a equipe ou você pode nos chamar por esse número direto. Qualquer outra coisa que eu possa ajudar? 🎶
