"""Loop de orquestração do agente: manda a mensagem pro modelo, executa
as ferramentas que ele pedir, e repete até ele ter uma resposta final.

Esse é o padrão padrão de "tool calling" / function calling no formato
da OpenAI (que a Groq implementa de forma compatível -- ver
config.GROQ_BASE_URL e a justificativa de provedor no README):

1. Manda `messages` (com o prompt de sistema na frente) + a lista de
   `tools` disponíveis pro modelo via `chat.completions.create`.
2. Se `finish_reason == "tool_calls"`, a mensagem de resposta do
   modelo trouxe um ou mais `tool_calls` -- cada um pedindo pra chamar
   uma função com certos argumentos (como uma string JSON).
3. O código (não o modelo) executa essas funções de verdade (ver
   tools.execute_tool) e manda o resultado de volta como uma mensagem
   de role="tool", referenciando o `tool_call_id` correspondente.
4. Repete até o modelo responder com `finish_reason == "stop"` -- aí o
   `content` da mensagem é a resposta final pro cliente.

Isso é diferente de um agente "ReAct" clássico com prompting manual
(tipo "Thought: ... Action: ... Observation: ..." em texto livre)
porque o tool calling da API já faz esse ciclo de forma estruturada --
não precisamos fazer parsing de texto pra extrair qual ferramenta o
modelo quer chamar e com quais parâmetros, o que seria mais frágil.
"""

from __future__ import annotations

import json

import openai

from . import config, tools
from .prompts import build_system_prompt

# Limite de idas e vindas de tool-calling dentro de UM turno de usuário.
# Existe só como rede de segurança contra um loop infinito (ex.: o
# modelo insistindo em chamar a mesma ferramenta com os mesmos
# parâmetros) -- nunca deveria ser atingido numa conversa normal, já
# que uma pergunta de atendimento raramente precisa de mais de 2-3
# chamadas de ferramenta encadeadas.
MAX_TOOL_ITERATIONS = 8


class EmporioAgent:
    """Encapsula o cliente (Groq via SDK da OpenAI) + o laço de tool calling.

    Mantém o client como atributo (em vez de recriar a cada chamada)
    porque o SDK reaproveita conexão HTTP entre requisições.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.client = openai.OpenAI(
            api_key=api_key or config.GROQ_API_KEY,
            base_url=config.GROQ_BASE_URL,
        )
        self.model = model or config.MODEL_NAME
        self.system_prompt = build_system_prompt()

    def send(self, messages: list[dict], user_text: str) -> tuple[str, list[dict]]:
        """Processa uma mensagem do usuário até chegar numa resposta final.

        Recebe o histórico anterior (`messages`, SEM a mensagem de
        sistema -- ela é adicionada aqui dentro a cada chamada, pois
        inclui a data/hora atual e não deveria "congelar" no que foi
        persistido de uma sessão antiga) e o texto novo do usuário.
        Devolve (texto_da_resposta, novo_historico_sem_sistema) -- quem
        chama (cli.py) decide o que fazer com o novo histórico
        (tipicamente, persistir via session.save_messages).
        """

        messages = [*messages, {"role": "user", "content": user_text}]

        final_text = ""
        for _ in range(MAX_TOOL_ITERATIONS):
            api_messages = [{"role": "system", "content": self.system_prompt}, *messages]
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=config.MAX_TOKENS,
                tools=tools.TOOLS,
                tool_choice="auto",
                messages=api_messages,
            )

            choice = response.choices[0]
            message = choice.message

            assistant_entry: dict = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                assistant_entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ]
            messages.append(assistant_entry)

            if not message.tool_calls:
                final_text = (message.content or "").strip()
                break

            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    result = {"error": f"Argumentos inválidos (JSON malformado): {tc.function.arguments!r}"}
                else:
                    result = tools.execute_tool(tc.function.name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
        else:
            # saiu do loop por exceder MAX_TOOL_ITERATIONS sem resposta final
            final_text = (
                "Desculpa, tive um problema pra terminar de consultar as informações "
                "necessárias. Pode tentar reformular sua pergunta, ou falar direto "
                "com um atendente humano?"
            )

        return final_text, messages
