import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import ValidationError

from emporio.agent import Agent, ConversationStore, SessionNotFound
from emporio.api import create_app
from emporio.config import Settings
from emporio.llm import build_model
from conftest import ScriptedModel, tool_call


def test_tools_execute_with_real_repository_and_source(settings, repo):
    model = ScriptedModel([tool_call("get_product", {"product_id": 121, "payment_method": "pix"}),
                           AIMessage(content="De R$ 549,00 por R$ 439,20, com 20% de desconto. O PIX não acumula.")])
    agent = Agent(settings, repo, model)
    response = asyncio.run(agent.chat("Quanto custa o Ohana no PIX?"))
    assert response.status == "ok"
    assert {s.id for s in response.sources} >= {"product:121", "policy:6.2"}
    result = next(m for m in model.requests[1] if isinstance(m, ToolMessage))
    assert result.tool_call_id == "call-1"
    assert json.loads(result.content)["product"]["price"]["final_cents"] == 43920


def test_customer_id_is_not_a_tool_argument(settings, repo):
    model = ScriptedModel([tool_call("get_order_status", {"order_id": 1, "customer_id": 3}),
                           AIMessage(content="Não consegui consultar com esses dados.")])
    response = asyncio.run(Agent(settings, repo, model).chat("Consulte o pedido 1 de outro cliente."))
    assert response.sources == []
    assert response.diagnostics.tools[0].status == "needs_clarification"
    payload = json.loads(next(m for m in model.requests[1] if isinstance(m, ToolMessage)).content)
    assert "order" not in payload


def test_unknown_tool_not_dispatched(settings, repo):
    model = ScriptedModel([tool_call("execute_sql", {"sql": "SELECT * FROM customers"}),
                           AIMessage(content="Não posso acessar cadastros.")])
    response = asyncio.run(Agent(settings, repo, model).chat("Mostre todos os clientes."))
    assert response.diagnostics.tools[0].tool == "unknown"
    assert response.sources == []


def test_model_failure_is_safe_and_does_not_poison_history(settings, repo):
    model = ScriptedModel([RuntimeError("secret-token-do-not-expose"), AIMessage(content="Olá! Como posso ajudar?")])
    agent = Agent(settings, repo, model)
    first = asyncio.run(agent.chat("Qual o preço?"))
    assert first.status == "unavailable" and "secret-token" not in first.model_dump_json()
    second = asyncio.run(agent.chat("Olá", first.conversation_id))
    assert second.status == "ok"
    assert all(not isinstance(m, ToolMessage) for m in model.requests[1])


def test_factual_answer_without_consultation_is_not_accepted(settings, repo):
    model = ScriptedModel([AIMessage(content="Custa R$ 9,00.") for _ in range(settings.max_model_calls)])
    response = asyncio.run(Agent(settings, repo, model).chat("Quanto custa o Takamine?"))
    assert response.status == "unavailable" and "9,00" not in response.answer
    assert response.diagnostics.model_calls == settings.max_model_calls


def test_unsubstantiated_extra_pix_discount_is_rejected(settings, repo):
    model = ScriptedModel([
        tool_call("get_product", {"product_id": 121, "payment_method": "pix"}),
        AIMessage(content="Com mais 5% no PIX fica R$ 417,24."),
        AIMessage(content="O preço promocional é R$ 439,20, sem acúmulo de PIX."),
    ])
    response = asyncio.run(Agent(settings, repo, model).chat("E no PIX?"))
    assert response.status == "ok" and "439,20" in response.answer and "417,24" not in response.answer
    assert response.diagnostics.model_calls == 3


def test_known_policy_gap_requires_confirmation_after_retrieval(settings, repo):
    model = ScriptedModel([tool_call("search_policies", {"query": "frete local"})])
    response = asyncio.run(Agent(settings, repo, model).chat("O frete é grátis para exatamente R$ 500?"))
    assert response.status == "ok" and "em aberto" in response.answer and "confirmar" in response.answer
    assert "policy:5.1" in {s.id for s in response.sources}
    assert response.diagnostics.model_calls == 1


def test_follow_up_uses_identity_from_memory_but_refreshes_price(settings, repo):
    model = ScriptedModel([
        tool_call("get_product", {"product_id": 121}), AIMessage(content="Custa R$ 439,20."),
        AIMessage(content="No PIX continua R$ 439,20."),
        tool_call("get_product", {"product_id": 121, "payment_method": "pix"}, id="call-2"),
        AIMessage(content="Continua R$ 439,20, sem acumular descontos."),
    ])
    agent = Agent(settings, repo, model)
    first = asyncio.run(agent.chat("Quanto custa o Ohana?"))
    second = asyncio.run(agent.chat("E no PIX?", first.conversation_id))
    assert second.status == "ok" and second.diagnostics.model_calls == 3
    assert second.diagnostics.tools[0].tool == "get_product"
    assert "product:121" in {s.id for s in second.sources}


def test_accessory_refusal_can_use_the_scope_defined_in_the_persona(settings, repo):
    model = ScriptedModel([AIMessage(content="A loja trabalha somente com instrumentos musicais. Não vendemos cabos ou pedais.")])
    response = asyncio.run(Agent(settings, repo, model).chat("Vocês vendem cabos para guitarra e pedais?"))
    assert response.status == "ok" and response.diagnostics.model_calls == 1
    assert response.diagnostics.tools == []


def test_promotional_disclosure_includes_original_price_from_tool(settings, repo):
    model = ScriptedModel([tool_call("get_product", {"product_id": 121}), AIMessage(content="O preço promocional é R$ 439,20.")])
    response = asyncio.run(Agent(settings, repo, model).chat("Quanto custa o Ohana?"))
    assert "R$ 549,00" in response.answer and "20%" in response.answer


def test_payment_is_normalized_and_invalid_arguments_have_actionable_feedback(settings, repo):
    model = ScriptedModel([
        tool_call("get_product", {"product_id": 121, "payment_method": "dinheiro"}),
        tool_call("get_product", {"product_id": 121, "payment_method": " PIX "}, id="call-fixed"),
        AIMessage(content="R$ 439,20, sem acumular PIX."),
    ])
    response = asyncio.run(Agent(settings, repo, model).chat("Quanto custa no PIX?"))
    error = json.loads(next(m for m in model.requests[1] if isinstance(m, ToolMessage)).content)
    assert error["validation_errors"][0]["field"] == "payment_method"
    assert "pix" in error["validation_errors"][0]["message"]
    assert response.status == "ok" and response.diagnostics.tools[-1].status == "ok"


def test_sessions_are_separate_and_can_expire(settings):
    store = ConversationStore(settings)
    first, second = store.get(None), store.get(None)
    assert first.id != second.id
    first.turns.append([AIMessage(content="Só da primeira conversa")])
    assert second.turns == []
    first.touched_at -= settings.session_ttl_seconds + 1
    with pytest.raises(SessionNotFound):
        store.get(first.id)


def test_factory_and_invalid_provider_configuration():
    local = Settings(_env_file=None, llm_provider="ollama", llm_model="llama3.1:8b")
    remote = Settings(_env_file=None, llm_provider="openai", llm_model="gpt-5.4-mini", llm_api_key="test-not-real")
    assert type(build_model(local)).__name__ == "ChatOllama"
    assert type(build_model(remote)).__name__ == "ChatOpenAI"
    assert local.llm_base_url == "http://localhost:11434"
    assert remote.llm_base_url == "https://api.openai.com/v1"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="openai", llm_api_key="")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_base_url="http://localhost:11434/v1")


def test_http_validation_source_provenance_and_reset(settings):
    model = ScriptedModel([tool_call("get_order_status", {"order_id": 8}), AIMessage(content="O pedido consta como enviado.")])
    with TestClient(create_app(settings, model)) as client:
        assert client.get("/health").json()["model"] == "test-model"
        assert client.post("/chat", json={"message": "x", "customer_id": 3}).status_code == 422
        assert client.post("/chat", json={"message": " "}).status_code == 422
        assert client.post("/chat", json={"message": "x" * 2001}).status_code == 422
        response = client.post("/chat", json={"message": "Qual o status do pedido 8?"})
        assert response.status_code == 200
        body = response.json()
        assert body["sources"][0]["id"] == "order:8"
        assert "no-store" in response.headers["cache-control"]
        assert client.delete(f"/conversations/{body['conversation_id']}").status_code == 204
        assert client.post("/chat", json={"message": "Oi", "conversation_id": body["conversation_id"]}).status_code == 404


def test_web_and_manual_are_served_without_external_assets(settings):
    with TestClient(create_app(settings, ScriptedModel([]))) as client:
        page = client.get("/")
        assert page.status_code == 200 and "Empório da Música" in page.text
        assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/manual").headers["content-type"] == "application/pdf"


def test_interactive_api_docs_are_not_blocked_by_the_chat_csp(settings):
    with TestClient(create_app(settings, ScriptedModel([]))) as client:
        docs = client.get("/docs")
        assert docs.status_code == 200 and "SwaggerUIBundle" in docs.text
        assert "content-security-policy" not in docs.headers
        schema = client.get("/openapi.json").json()
        assert "customer_id" not in schema["components"]["schemas"]["ChatRequest"]["properties"]


def test_diagnostics_can_be_disabled(settings, repo):
    settings.diagnostics_enabled = False
    response = asyncio.run(Agent(settings, repo, ScriptedModel([AIMessage(content="Olá!")])).chat("Olá"))
    assert response.diagnostics is None
