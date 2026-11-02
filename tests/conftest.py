from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from emporio.config import ROOT, Settings
from emporio.ingest import build_database
from emporio.repository import Repository


@pytest.fixture(scope="session")
def database(tmp_path_factory):
    path = tmp_path_factory.mktemp("database") / "test.sqlite3"
    build_database(ROOT / "data", path)
    return path


@pytest.fixture
def repo(database):
    return Repository(database, customer_id=2)


@pytest.fixture
def settings(database):
    return Settings(_env_file=None, database_path=database, llm_model="test-model", diagnostics_enabled=True)


class ScriptedModel:
    """Substitui somente a rede/modelo, preservando ferramentas e mensagens reais."""
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def bind_tools(self, tools):
        self.tools = tools
        return self

    async def ainvoke(self, messages):
        self.requests.append(list(messages))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def tool_call(name, args, id="call-1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id, "type": "tool_call"}])
