"""Loop limitado e inspecionável, compartilhado por CLI e API."""

import asyncio
import json
import re
import time
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field, ValidationError

from .config import Settings
from .policies import normalize, required_clarification
from .prompts import SYSTEM_PROMPT
from .repository import Repository
from .responses import polish_response
from .tools import build_tools


class Source(BaseModel):
    id: str
    kind: Literal["product", "promotion", "policy", "order"]
    label: str
    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class ToolEvent(BaseModel):
    tool: str
    status: str
    duration_ms: int
    source_count: int


class Diagnostics(BaseModel):
    provider: str
    model: str
    model_calls: int
    elapsed_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    tools: list[ToolEvent] = Field(default_factory=list)


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    status: Literal["ok", "unavailable"] = "ok"
    sources: list[Source] = Field(default_factory=list)
    diagnostics: Diagnostics | None = None


@dataclass
class Conversation:
    id: str = field(default_factory=lambda: uuid4().hex)
    turns: list[list[BaseMessage]] = field(default_factory=list)
    touched_at: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_product_id: int | None = None


class SessionNotFound(Exception):
    pass


class SessionCapacity(Exception):
    pass


class SessionBusy(Exception):
    pass


class ConversationStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sessions: dict[str, Conversation] = {}

    def get(self, conversation_id: str | None) -> Conversation:
        now = time.monotonic()
        expired = [key for key, session in self.sessions.items()
                   if now - session.touched_at > self.settings.session_ttl_seconds and not session.lock.locked()]
        for key in expired:
            del self.sessions[key]
        if conversation_id:
            if conversation_id not in self.sessions:
                raise SessionNotFound
            session = self.sessions[conversation_id]
            session.touched_at = now
            return session
        if len(self.sessions) >= self.settings.max_sessions:
            raise SessionCapacity
        session = Conversation()
        self.sessions[session.id] = session
        return session

    def delete(self, conversation_id: str) -> None:
        session = self.sessions.get(conversation_id)
        if session and session.lock.locked():
            raise SessionBusy
        self.sessions.pop(conversation_id, None)


def message_text(message: AIMessage) -> str:
    if isinstance(message.content, str):
        text = message.content
    else:
        text = "\n".join(b.get("text", "") for b in message.content
                         if isinstance(b, dict) and b.get("type") == "text")
    # Alguns servidores incluem delimitadores mesmo com reasoning desabilitado.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return re.sub(r"\*\*([^*]+)\*\*", r"\1", text).strip()


def needs_evidence(text: str) -> bool:
    q = normalize(text)
    # O escopo é parte da persona, extraída do manual. Recusar um acessório
    # não exige consultar estoque/preço de um produto que não comercializamos.
    accessory = re.search(r"\b(cabos?|pedais|pedal|palhetas?|amplificadores?|cases?)\b", q)
    operational = any(word in q for word in ("pedido", "devol", "troca", "garantia", "frete", "entrega"))
    if accessory and not operational:
        return False
    return any(word in q for word in (
        "prec", "custa", "valor", "estoque", "dispon", "pedido", "rastre", "pix", "promoc", "desconto",
        "horario", "abre", "funciona", "endereco", "whatsapp", "telefone", "frete", "entrega", "devol",
        "troca", "garantia", "parcel", "cartao", "boleto", "opcoes", "violao", "violoes", "guitarra",
        "ukulele", "takamine", "yamaha", "ohana", "kalani", "loja", "emporio", "cabo", "pedal",
    ))


def money_values(text: str) -> set[int]:
    """Compara valores explícitos em reais; não interpreta a política comercial."""
    values = set()
    for match in re.finditer(r"R\$\s*(\d[\d.]*)(?:,(\d{1,2}))?", text):
        whole, fraction = match.groups()
        if fraction is not None:
            number = Decimal(whole.replace(".", "") + "." + fraction.ljust(2, "0"))
        elif "." in whole and len(whole.rsplit(".", 1)[1]) in (1, 2):
            number = Decimal(whole)
        else:
            number = Decimal(whole.replace(".", ""))
        values.add(int(number * 100))
    return values


class Agent:
    def __init__(self, settings: Settings, repository: Repository, model):
        self.settings = settings
        self.repository = repository
        self.tools = build_tools(repository)
        self.model = model.bind_tools(list(self.tools.values()))
        self.sessions = ConversationStore(settings)

    async def chat(self, text: str, conversation_id: str | None = None) -> ChatResponse:
        session = self.sessions.get(conversation_id)
        if session.lock.locked():
            raise SessionBusy
        async with session.lock:
            return await self._run(session, text)

    async def _run(self, session: Conversation, text: str) -> ChatResponse:
        started = time.monotonic()
        today = datetime.now(ZoneInfo("America/Campo_Grande")).date().isoformat()
        system = SystemMessage(content=SYSTEM_PROMPT + f"\nData da execução: {today}.")
        if session.last_product_id is not None:
            system.content += (f"\nProduto da conversa anterior: ID {session.last_product_id}. "
                               "Isso resolve referências como 'ele', mas não substitui consultar get_product "
                               "novamente para preço/PIX. Se o cliente perguntar outro nome, faça uma nova busca.")
        previous = session.turns[-self.settings.max_history_turns:]
        # Remover turnos completos preserva o protocolo de chamada/resultado.
        while previous and sum(len(str(m.content)) for turn in previous for m in turn) > 12000:
            previous = previous[1:]
        messages = [system, *(m for turn in previous for m in turn)]
        turn: list[BaseMessage] = [HumanMessage(content=text)]
        sources: dict[str, Source] = {}
        events: list[ToolEvent] = []
        allowed_money = money_values(text)
        promotions: dict[int, dict] = {}
        model_calls = 0
        input_tokens = output_tokens = 0
        measured_usage = False
        answer = "Não consegui concluir essa consulta agora. Tente novamente ou peça ajuda à equipe da loja."
        status = "unavailable"
        completed = False
        try:
            for _ in range(self.settings.max_model_calls):
                model_calls += 1
                result = await asyncio.wait_for(
                    self.model.ainvoke(messages + turn), timeout=self.settings.llm_timeout_seconds,
                )
                if not isinstance(result, AIMessage):
                    raise TypeError("Formato inesperado de resposta do modelo.")
                if result.usage_metadata:
                    measured_usage = True
                    input_tokens += result.usage_metadata.get("input_tokens", 0)
                    output_tokens += result.usage_metadata.get("output_tokens", 0)
                turn.append(result)
                calls = result.tool_calls
                if result.invalid_tool_calls:
                    answer = "O modelo não conseguiu montar uma consulta válida. Pode reformular a pergunta?"
                    break
                if not calls:
                    candidate = polish_response(message_text(result))
                    values = money_values(candidate)
                    if candidate and not events and (needs_evidence(text) or values):
                        turn.pop()
                        hint = (f" Para o produto anterior use get_product com product_id={session.last_product_id}."
                                if session.last_product_id else "")
                        turn.append(HumanMessage(content="Antes de responder à pergunta original, consulte a ferramenta adequada NESTA mensagem. O histórico não é uma consulta atual." + hint,
                                                 additional_kwargs={"application_note": True}))
                        continue
                    if values - allowed_money:
                        turn.pop()
                        turn.append(HumanMessage(content="Sua resposta incluiu um valor em reais sem suporte no resultado consultado. Reescreva usando somente os valores retornados pelas ferramentas; não acumule descontos nem faça novo cálculo.",
                                                 additional_kwargs={"application_note": True}))
                        continue
                    if candidate and (events or not (needs_evidence(text) or values)):
                        disclosures = []
                        for product in promotions.values():
                            price = product["price"]
                            if price["final_cents"] in values and price["original_cents"] not in values:
                                disclosures.append(f"{product['name']}: de {price['original_price']} por {price['final_price']} ({price['discount_percent']}% de desconto). O PIX não acumula com essa promoção.")
                        if disclosures:
                            candidate += "\n\n" + "\n".join(disclosures)
                        result.content = candidate
                        answer, status, completed = candidate, "ok", True
                        break
                    turn.append(HumanMessage(content="Antes de responder, consulte a ferramenta adequada. Não afirme fatos da loja sem uma consulta nesta mensagem.",
                                             additional_kwargs={"application_note": True}))
                    continue
                if len(events) + len(calls) > self.settings.max_tool_calls_per_turn:
                    answer = "Essa solicitação exigiu consultas demais. Vamos tratar uma pergunta por vez?"
                    break
                for call in calls:
                    tick = time.monotonic()
                    name = call["name"]
                    try:
                        if name not in self.tools:
                            payload = {"status": "error", "message": "Ferramenta não autorizada.", "sources": []}
                        else:
                            tool = self.tools[name]
                            args = tool.args_schema.model_validate(call["args"]).model_dump()
                            payload = tool.func(**args)
                    except ValidationError as error:
                        payload = {"status": "needs_clarification", "message": "Argumentos inválidos. Corrija os campos indicados e tente a ferramenta novamente, sem acrescentar campos extras.",
                                   "validation_errors": [{"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
                                                         for item in error.errors(include_input=False, include_context=False, include_url=False)],
                                   "sources": []}
                    except Exception:
                        payload = {"status": "error", "message": "Não foi possível consultar esta fonte agora. Não invente o resultado.", "sources": []}
                    for raw in payload.get("sources", []):
                        source = Source.model_validate(raw)
                        sources[source.id] = source
                    payload_text = json.dumps(payload, ensure_ascii=False, default=str)
                    allowed_money.update(money_values(payload_text))
                    product = payload.get("product")
                    if not product and len(payload.get("products", [])) == 1:
                        product = payload["products"][0]
                    if "products" in payload and len(payload["products"]) != 1:
                        session.last_product_id = None
                    if product:
                        session.last_product_id = product["product_id"]
                    quoted_products = payload.get("products", []) + ([payload["product"]] if payload.get("product") else [])
                    for quoted in quoted_products:
                        if quoted.get("price") and quoted["price"]["discount_origin"] == "promotion":
                            promotions[quoted["product_id"]] = quoted
                    events.append(ToolEvent(tool=name if name in self.tools else "unknown",
                                            status=payload["status"], duration_ms=round((time.monotonic() - tick) * 1000),
                                            source_count=len(payload.get("sources", []))))
                    turn.append(ToolMessage(content=payload_text,
                                            tool_call_id=call["id"], name=name))
                    clarification = required_clarification(text, payload)
                    if clarification:
                        answer, status, completed = clarification, "ok", True
                if completed:
                    turn.append(AIMessage(content=answer))
                    break
        except Exception:
            # Mensagens de exceção do provedor podem conter URLs ou metadados privados.
            # Resposta pública estável; sem registrar prompts, chaves ou retornos brutos.
            answer = "Não consegui acessar o modelo agora. Verifique se o Ollama está em execução e o modelo está instalado, ou revise a configuração do provedor. Você pode tentar novamente."
        if completed:
            clean_turn = [m for m in turn if not m.additional_kwargs.get("application_note")]
            session.turns = [*previous, clean_turn][-self.settings.max_history_turns:]
        else:
            # Não guardar chamadas incompletas num histórico que será reenviado.
            session.turns = [*previous, [HumanMessage(content=text), AIMessage(content=answer)]][-self.settings.max_history_turns:]
        session.touched_at = time.monotonic()
        diagnostics = None
        if self.settings.diagnostics_enabled:
            diagnostics = Diagnostics(
                provider=self.settings.llm_provider, model=self.settings.llm_model, model_calls=model_calls,
                elapsed_ms=round((time.monotonic() - started) * 1000), tools=events,
                input_tokens=input_tokens if measured_usage else None,
                output_tokens=output_tokens if measured_usage else None,
            )
        return ChatResponse(conversation_id=session.id, answer=answer, status=status,
                            sources=list(sources.values()), diagnostics=diagnostics)
