"""Testes de session.py, com foco no corte de histórico por turnos.

O ponto delicado testado aqui: tool_use (assistant) e tool_result
(user, mas com content em lista, não string) precisam ficar
emparelhados depois do corte -- um corte no meio quebraria a próxima
chamada à API da Anthropic.
"""

import json

from emporio_agent import session


def _user(text):
    return {"role": "user", "content": text}


def _assistant_text(text):
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def _assistant_tool_use(tool_id, name, input_):
    return {"role": "assistant", "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": input_}]}


def _tool_result(tool_id, result):
    return {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": json.dumps(result)}],
    }


def test_trim_keeps_everything_when_under_limit():
    messages = [_user("oi"), _assistant_text("olá!")]
    assert session.trim_to_last_turns(messages, max_turns=5) == messages


def test_trim_cuts_at_turn_boundary_not_in_the_middle_of_tool_pair():
    messages = [
        _user("quanto custa o Takamine GD20?"),
        _assistant_tool_use("t1", "get_product_details", {"identifier": "Takamine GD20"}),
        _tool_result("t1", {"found": True}),
        _assistant_text("Custa R$ 2.199,00!"),
        _user("e o Martin D-28?"),
        _assistant_tool_use("t2", "get_product_details", {"identifier": "Martin D-28"}),
        _tool_result("t2", {"found": True}),
        _assistant_text("Esse custa R$ 11.499,00."),
    ]
    trimmed = session.trim_to_last_turns(messages, max_turns=1)
    # deve começar exatamente no segundo "turno real" (a segunda
    # pergunta em texto puro do usuário), nunca no meio do par
    # tool_use/tool_result do primeiro turno
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
