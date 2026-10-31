"""Loop de orquestração do agente: manda a mensagem pro modelo, executa
as ferramentas que ele pedir, e repete até ele ter uma resposta final.

Esse é o padrão padrão de "tool use" / function calling da Anthropic:
1. Manda `messages` + a lista de `tools` disponíveis pro modelo.
2. Se o modelo responder com `stop_reason == "tool_use"`, ele incluiu
   um ou mais blocos `tool_use` no conteúdo da resposta -- cada um
   pedindo pra chamar uma função com certos parâmetros.
3. O código (não o modelo) executa essas funções de verdade (ver
   tools.execute_tool) e manda o resultado de volta como uma nova
   mensagem de role="user" com blocos `tool_result`.
4. Repete até o modelo responder com `stop_reason == "end_turn"`
   (ou similar) -- aí o texto da resposta é a resposta final pro
   cliente.

Isso é diferente de um agente "ReAct" clássico com prompting manual
(tipo "Thought: ... Action: ... Observation: ...") porque o
tool-use da Anthropic já faz esse ciclo de forma estruturada e
nativa da API -- não precisamos fazer parsing de texto livre pra
extrair qual ferramenta o modelo quer chamar, o que é mais frágil.
"""

from __future__ import annotations

import json

import anthropic

from . import config, tools
from .prompts import build_system_prompt

# Limite de idas e vindas de tool-use dentro de UM turno de usuário.
# Existe só como rede de segurança contra um loop infinito (ex.: o
# modelo insistindo em chamar a mesma ferramenta com os mesmos
# parâmetros) -- nunca deveria ser atingido numa conversa normal, já
# que uma pergunta de atendimento raramente precisa de mais de 2-3
# chamadas de ferramenta encadeadas.
MAX_TOOL_ITERATIONS = 8


class EmporioAgent:
    """Encapsula o cliente da Anthropic + o laço de tool-use.

    Mantém o client como atributo (em vez de recriar a cada chamada)
    porque o SDK reaproveita conexão HTTP entre requisições.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.client = anthropic.Anthropic(api_key=api_key or config.ANTHROPIC_API_KEY)
        self.model = model or config.MODEL_NAME
        self.system_prompt = build_system_prompt()

    def send(self, messages: list[dict], user_text: str) -> tuple[str, list[dict]]:
        """Processa uma mensagem do usuário até chegar numa resposta final.

        Recebe o histórico anterior (`messages`, no formato de
        `messages` da API) e o texto novo do usuário. Devolve
        (texto_da_resposta, novo_historico_completo) -- quem chama
        (cli.py) decide o que fazer com o novo histórico (tipicamente,
        persistir via session.save_messages).
        """

        messages = [*messages, {"role": "user", "content": user_text}]

        final_text = ""
        for _ in range(MAX_TOOL_ITERATIONS):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=config.MAX_TOKENS,
                system=self.system_prompt,
                tools=tools.TOOLS,
                messages=messages,
            )

            assistant_content = [_serialize_content_block(b) for b in response.content]
            messages.append({"role": "assistant", "content": assistant_content})

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            if not tool_use_blocks:
                final_text = _extract_text(response.content)
                break

            tool_results = []
            for block in tool_use_blocks:
                result = tools.execute_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                        "is_error": "error" in result,
                    }
                )
            messages.append({"role": "user", "content": tool_results})
        else:
            # saiu do loop por exceder MAX_TOOL_ITERATIONS sem resposta final
            final_text = (
                "Desculpa, tive um problema pra terminar de consultar as informações "
                "necessárias. Pode tentar reformular sua pergunta, ou falar direto "
                "com um atendente humano?"
            )

        return final_text, messages


def _extract_text(content_blocks) -> str:
    return "".join(b.text for b in content_blocks if b.type == "text").strip()


def _serialize_content_block(block) -> dict:
    """Converte um bloco de resposta do SDK (objeto pydantic) num dict
    simples, só com os campos que o próprio formato de `messages` da
    API espera de volta.

    Não usamos `block.model_dump()` direto: ele inclui campos só de
    resposta (ex.: `citations`, `caller`) que não fazem parte do
    schema de entrada (`MessageParam`) e, em tese, poderiam ser
    rejeitados pela API num request futuro. Serializar explicitamente
    por tipo é mais verboso, mas deixa claro exatamente o que
    persistimos e reenviamos.
    """

    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    # outros tipos de bloco (ex.: thinking, se algum dia habilitado) --
    # preserva como dict genérico em vez de quebrar
    return block.model_dump()
