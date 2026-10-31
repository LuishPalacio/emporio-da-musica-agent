"""Testes de session.py, com foco no corte de histórico por turnos.

Os helpers abaixo montam mensagens no mesmo formato que agent.py
realmente produz (chat completions da OpenAI/Groq): uma chamada de
ferramenta é um `tool_calls` dentro da mensagem do assistant (não um
bloco de conteúdo separado como no formato nativo da Anthropic), e o
resultado da ferramenta é uma mensagem própria com role="tool" (não
role="user" como seria no formato da Anthropic). O ponto delicado
testado aqui: uma mensagem assistant-com-tool_calls e a(s)
mensagem(ns) role="tool" que a seguem precisam ficar emparelhadas
depois do corte -- um corte no meio quebraria a próxima chamada à API
(ela exige um resultado para cada tool_call pendente).
"""

import json

from emporio_agent import session


def _user(text):
    return {"role": "user", "content": text}


def _assistant_text(text):
    return {"role": "assistant", "content": text}


def _assistant_tool_call(tool_id, name, input_):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": tool_id, "type": "function", "function": {"name": name, "arguments": json.dumps(input_)}}
        ],
    }


def _tool_result(tool_id, result):
    return {"role": "tool", "tool_call_id": tool_id, "content": json.dumps(result)}


def test_trim_keeps_everything_when_under_limit():
    messages = [_user("oi"), _assistant_text("olá!")]
    assert session.trim_to_last_turns(messages, max_turns=5) == messages


def test_trim_cuts_at_turn_boundary_not_in_the_middle_of_tool_pair():
    messages = [
        _user("quanto custa o Takamine GD20?"),
        _assistant_tool_call("t1", "get_product_details", {"identifier": "Takamine GD20"}),
        _tool_result("t1", {"found": True}),
        _assistant_text("Custa R$ 2.199,00!"),
        _user("e o Martin D-28?"),
        _assistant_tool_call("t2", "get_product_details", {"identifier": "Martin D-28"}),
        _tool_result("t2", {"found": True}),
        _assistant_text("Esse custa R$ 11.499,00."),
    ]
    trimmed = session.trim_to_last_turns(messages, max_turns=1)
    # deve começar exatamente no segundo "turno real" (a segunda
    # pergunta em texto puro do usuário), nunca no meio do par
    # assistant-tool_calls / tool-result do primeiro turno
    assert trimmed[0] == _user("e o Martin D-28?")
    assert trimmed[0]["role"] == "user" and isinstance(trimmed[0]["content"], str)


def test_trim_two_turns():
    messages = [
        _user("pergunta 1"),
        _assistant_text("resposta 1"),
        _user("pergunta 2"),
        _assistant_text("resposta 2"),
        _user("pergunta 3"),
        _assistant_text("resposta 3"),
    ]
    trimmed = session.trim_to_last_turns(messages, max_turns=2)
    assert trimmed == messages[2:]


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(session.config, "CONVERSATIONS_DIR", tmp_path)
    messages = [_user("oi"), _assistant_text("olá!")]
    session.save_messages("teste123", messages)
    assert session.load_messages("teste123") == messages


def test_load_nonexistent_session_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(session.config, "CONVERSATIONS_DIR", tmp_path)
    assert session.load_messages("nao-existe") == []


def test_session_id_is_filesystem_safe():
    sid = session.new_session_id()
    assert all(c.isalnum() or c in "-_" for c in sid)
