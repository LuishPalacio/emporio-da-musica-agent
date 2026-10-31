"""Persistência de conversas em disco (JSON por sessão).

Por que persistir: um atendimento por chat raramente acontece num
turno só, e perder o histórico a cada reinício do processo seria uma
experiência ruim — o cliente teria que re-explicar o pedido toda vez.
Cada conversa vira um arquivo `conversations/<session_id>.json` com a
lista de mensagens no formato de `messages` da API (role + content,
compatível com o formato OpenAI/Groq usado em agent.py), então
carregar uma sessão de volta é simplesmente
desserializar o JSON direto no parâmetro `messages` da próxima
chamada — sem um formato intermediário próprio pra manter.

Por que arquivo e não um banco: o volume (poucas conversas, cada uma
pequena) não justifica outra tabela no MySQL, e um arquivo por sessão
facilita inspecionar/debugar uma conversa específica só abrindo o
arquivo.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import config

_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_-]")


def new_session_id() -> str:
    """Gera um ID de sessão legível e ordenável por data: 20260131-142301-ab12."""

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    import secrets

    return f"{stamp}-{secrets.token_hex(2)}"


def _session_path(session_id: str) -> Path:
    # sanitiza o id antes de usar como nome de arquivo -- evita path
    # traversal (".." etc.) se o id algum dia vier de uma fonte externa
    # (ex.: um parâmetro de URL, numa futura API HTTP)
    safe_id = _SAFE_ID_RE.sub("_", session_id)
    config.CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    return config.CONVERSATIONS_DIR / f"{safe_id}.json"


def load_messages(session_id: str) -> list[dict]:
    """Carrega o histórico de uma sessão. Sessão nova -> lista vazia."""

    path = _session_path(session_id)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_messages(session_id: str, messages: list[dict]) -> None:
    path = _session_path(session_id)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(messages, fh, ensure_ascii=False, indent=2, default=str)


def list_sessions() -> list[str]:
    config.CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.stem for p in config.CONVERSATIONS_DIR.glob("*.json"))


def trim_to_last_turns(messages: list[dict], max_turns: int) -> list[dict]:
    """Mantém só os últimos `max_turns` turnos reais de conversa.

    Evita que uma conversa longa estoure o contexto/custo do modelo a
    cada chamada. O ponto delicado: tool_use (lado assistant) e
    tool_result (lado user, mas não é uma mensagem "de verdade" do
    cliente) precisam continuar emparelhados -- cortar no meio de um
    par quebra a próxima chamada à API. Por isso um "turno" aqui é
    definido como começando numa mensagem de role="user" cujo content
    é uma string pura (uma mensagem de chat real, não um tool_result,
    que sempre tem content como lista de blocos). Cortar exatamente
    nesses pontos nunca separa um tool_use do seu tool_result.
    """

    turn_starts = [
        i for i, m in enumerate(messages) if m.get("role") == "user" and isinstance(m.get("content"), str)
    ]
    if len(turn_starts) <= max_turns:
        return messages
    cutoff = turn_starts[-max_turns]
    return messages[cutoff:]
