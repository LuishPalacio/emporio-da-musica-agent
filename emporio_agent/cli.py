"""Interface de linha de comando: um chat de atendimento no terminal.

Rodar com `python -m emporio_agent.cli`. Dois modos:
- Interativo (padrão): fica num loop lendo mensagens do teclado.
- Uma mensagem só (`--message "..."`): processa uma mensagem e sai --
  útil pra automatizar/testar sem precisar digitar interativamente
  (foi assim que os exemplos de conversa em examples/ foram gerados).

Um CLI foi escolhido como interface porque o enunciado do desafio
pede só "o agente funcionando corretamente" e deixa a interface em
aberto -- um CLI é o jeito mais direto de demonstrar o laço de
conversa completo (incluindo chamadas de ferramenta e persistência de
sessão) sem o overhead de montar uma API HTTP ou front-end só pra
avaliação. Ver README para a reflexão sobre uma interface de API/HTTP
como próximo passo.
"""

from __future__ import annotations

import argparse
import sys

from . import config, database, session
from .agent import EmporioAgent

# O console do Windows abre em cp1252 (ou outra codepage legada) por
# padrão, não em UTF-8 -- e o modelo eventualmente responde com um
# emoji ou outro caractere fora do cp1252 (ex.: 😊), o que derrubava o
# processo inteiro com UnicodeEncodeError no print(). reconfigure()
# (Python 3.7+) força stdout/stderr para UTF-8 com errors="replace"
# como rede de segurança, sem exigir que quem rode o projeto troque a
# codepage do terminal manualmente (`chcp 65001`) antes de usar o CLI.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _check_api_key() -> None:
    if not config.GROQ_API_KEY:
        print(
            "ERRO: variável de ambiente GROQ_API_KEY não encontrada.\n"
            "Copie .env.example para .env e preencha com sua chave gratuita "
            "(https://console.groq.com/keys).",
            file=sys.stderr,
        )
        sys.exit(1)


def _check_database() -> None:
    try:
        database.ensure_database()
    except ConnectionError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)


def run_interactive(session_id: str) -> None:
    history = session.load_messages(session_id)
    agent = EmporioAgent()

    print("=" * 60)
    print("  Empório da Música -- atendimento (protótipo)")
    print(f"  sessão: {session_id}")
    print("  digite 'sair' para encerrar")
    print("=" * 60)

    if not history:
        print("\nSol: Oi! Seja bem-vindo(a) à Empório da Música. Como posso te ajudar hoje?")

    while True:
        try:
            user_text = input("\nVocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nAté mais!")
            break

        if not user_text:
            continue
        if user_text.lower() in {"sair", "exit", "quit"}:
            print("\nSol: Até mais, volte sempre!")
            break

        trimmed = session.trim_to_last_turns(history, config.MAX_HISTORY_TURNS)
        reply, updated_trimmed = agent.send(trimmed, user_text)

        # só as mensagens novas desse turno (o resto de `updated_trimmed`
        # já estava em `history`) -- ver docstring de session.trim_to_last_turns
        new_messages = updated_trimmed[len(trimmed):]
        history = history + new_messages
        session.save_messages(session_id, history)

        print(f"\nSol: {reply}")


def run_single_message(session_id: str, message: str) -> None:
    history = session.load_messages(session_id)
    agent = EmporioAgent()

    trimmed = session.trim_to_last_turns(history, config.MAX_HISTORY_TURNS)
    reply, updated_trimmed = agent.send(trimmed, message)
    new_messages = updated_trimmed[len(trimmed):]
    history = history + new_messages
    session.save_messages(session_id, history)

    print(reply)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente de atendimento da Empório da Música")
    parser.add_argument(
        "--session", help="ID de uma sessão existente para continuar (padrão: cria uma nova)."
    )
    parser.add_argument(
        "--message", help="Processa uma única mensagem e sai, em vez de abrir o chat interativo."
    )
    parser.add_argument(
        "--rebuild-db", action="store_true", help="Força reconstruir o banco a partir dos CSVs antes de iniciar."
    )
    args = parser.parse_args()

    _check_api_key()
    if args.rebuild_db:
        database.ensure_database(force_rebuild=True)
    _check_database()

    session_id = args.session or session.new_session_id()

    if args.message:
        run_single_message(session_id, args.message)
    else:
        run_interactive(session_id)


if __name__ == "__main__":
    main()
