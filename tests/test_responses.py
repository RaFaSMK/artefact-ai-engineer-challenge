import asyncio

import pytest
from langchain_core.messages import AIMessage

from conftest import ScriptedModel, tool_call
from emporio.agent import Agent
from emporio.responses import CAPABILITIES, polish_response


@pytest.mark.parametrize("closing", [
    "Gostaria de agendar uma visita à loja?",
    "Deseja que eu reserve o produto?",
    "Quer finalizar a compra?",
    "Posso te ajudar a agendar uma visita?",
    "Vou registrar sua solicitação.",
    "Podemos cancelar o pedido agora?",
    "Would you like more details?",
])
def test_removes_unsupported_offers_but_preserves_product_price(closing):
    original = "O modelo custa R$ 439,20 e tem 6 unidades no snapshot. " + closing
    answer = polish_response(original)
    assert "R$ 439,20" in answer and "6 unidades" in answer
    assert closing not in answer
    assert "Posso ajudar com mais informações" in answer


@pytest.mark.parametrize("text", [
    "Não posso agendar uma visita por este chat.",
    "Não registrei nenhuma solicitação.",
    "Posso mostrar opções de ukuleles?",
    "Gostaria de marcas como Yamaha e Tagima?",
    "O modelo tem tampo Spruce e formato Dreadnought.",
    "O pedido consta como enviado.",
    "O reembolso será realizado conforme as condições do manual.",
])
def test_preserves_informational_and_negated_statements(text):
    assert polish_response(text) == text


@pytest.mark.parametrize("claim", ["Agendei sua visita.", "Já reservei o instrumento.", "Registrei a reclamação."])
def test_replaces_false_execution_claim_with_actual_capabilities(claim):
    answer = polish_response(claim)
    assert claim not in answer
    assert CAPABILITIES in answer


def test_corrects_observed_language_mix_without_changing_catalog_terms():
    text = "Se precisar de ajuda com algo else, estou à disposição! Tampo Spruce sólido."
    answer = polish_response(text)
    assert "else" not in answer and "mais alguma coisa" in answer
    assert "Spruce sólido" in answer


def test_delivered_text_and_history_use_the_same_polished_response(settings, repo):
    model = ScriptedModel([
        tool_call("get_product", {"product_id": 121}),
        AIMessage(content="O preço é R$ 439,20. Gostaria de agendar uma visita?"),
    ])
    agent = Agent(settings, repo, model)
    response = asyncio.run(agent.chat("Quanto custa o Ohana?"))
    assert response.status == "ok" and "agendar uma visita" not in response.answer
    assert "R$ 439,20" in response.answer and "R$ 549,00" in response.answer
    session = agent.sessions.get(response.conversation_id)
    assert session.turns[-1][-1].content == response.answer
