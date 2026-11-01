"""Entradas executáveis: python -m emporio ingest|serve|chat."""

import argparse
import asyncio
import json

from .agent import Agent
from .config import Settings
from .ingest import build_database
from .llm import build_model
from .repository import Repository


async def run_chat(settings):
    if not settings.database_path.exists():
        build_database(settings.data_dir, settings.database_path)
    agent = Agent(settings, Repository(settings.database_path, settings.demo_customer_id), build_model(settings))
    conversation_id = None
    print(f"Empório da Música · {settings.llm_provider}/{settings.llm_model}")
    print("/nova limpa a conversa · /sair encerra · dados do snapshot do desafio")
    while True:
        try:
            text = input("\nVocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text == "/sair":
            break
        if text == "/nova":
            if conversation_id:
                agent.sessions.delete(conversation_id)
            conversation_id = None
            print("Nova conversa.")
            continue
        if not text:
            continue
        if len(text) > 2000:
            print("Use até 2.000 caracteres por mensagem.")
            continue
        response = await agent.chat(text, conversation_id)
        conversation_id = response.conversation_id
        print("\nAssistente:", response.answer)
        for source in response.sources:
            print("  Fonte:", source.label)
        if response.diagnostics:
            print("  Consultas:", ", ".join(e.tool for e in response.diagnostics.tools) or "nenhuma")


def main():
    parser = argparse.ArgumentParser(description="Atendimento da Empório da Música")
    parser.add_argument("command", choices=["ingest", "serve", "chat"])
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    settings = Settings()
    if args.command == "ingest":
        print(json.dumps(build_database(settings.data_dir, settings.database_path), ensure_ascii=False, indent=2))
    elif args.command == "serve":
        import uvicorn
        from .api import create_app
        uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port)
    else:
        asyncio.run(run_chat(settings))


if __name__ == "__main__":
    main()
