"""Quatro ferramentas com schemas fechados e contexto de acesso no backend."""

from decimal import Decimal
from typing import Annotated, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from .repository import Repository

Payment = Annotated[
    Literal["pix", "credit", "debit", "boleto"],
    BeforeValidator(lambda value: value.strip().lower() if isinstance(value, str) else value),
]


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchProducts(Arguments):
    query: str = Field(default="", max_length=160, description="Somente nome, marca ou modelo. Use category para tipo de instrumento.")
    category: str | None = Field(default=None, max_length=80, description="Ex.: violão, ukulele, guitarra, baixo.")
    max_price_brl: Decimal | None = Field(default=None, ge=0, le=1_000_000, allow_inf_nan=False, description="Orçamento em reais sobre preço final na condição informada.")
    payment_method: Payment | None = Field(default=None, description="PIX apenas se o cliente informar essa condição.")
    limit: int = Field(default=5, ge=1, le=5)


class GetProduct(Arguments):
    product_id: int = Field(gt=0, description="ID retornado por search_products, nunca adivinhar.")
    payment_method: Payment | None = None


class GetOrder(Arguments):
    order_id: int = Field(gt=0)


class SearchPolicies(Arguments):
    query: str = Field(min_length=2, max_length=400, description="Pergunta ou assunto da política em português.")


def build_tools(repository: Repository) -> dict[str, StructuredTool]:
    definitions = [
        ("search_products", repository.search_products, SearchProducts,
         "Busca produtos por nome/modelo e/ou categoria, com estoque, preço calculado e promoção ativa. Use antes de responder valores ou recomendar instrumentos. Não use frase inteira em query: extraia nome/modelo; orçamento e categoria têm campos próprios."),
        ("get_product", repository.get_product, GetProduct,
         "Consulta detalhe e preço de um produto por ID obtido da busca. Usar também para recalcular a condição PIX em uma continuação. Não confirma disponibilidade por memória."),
        ("get_order_status", repository.get_order_status, GetOrder,
         "Consulta status e previsão registrada de pedido do cliente da sessão de demonstração. Não recebe customer_id. Não executa cancelamento, rastreamento externo nem devolução."),
        ("search_policies", repository.search_policies, SearchPolicies,
         "Consulta o manual para horários, endereço, pagamentos, PIX, parcelamento, frete, trocas, devoluções, garantia e escopo. Retorna seções, fontes e notas de ambiguidade que devem ser respeitadas."),
    ]
    return {name: StructuredTool.from_function(func=fn, name=name, description=description, args_schema=schema)
            for name, fn, schema, description in definitions}
