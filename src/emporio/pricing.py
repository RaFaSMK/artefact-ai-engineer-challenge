"""Dinheiro e descontos são calculados em Python, fora do modelo."""

from decimal import Decimal, ROUND_HALF_UP


class PromotionConflict(ValueError):
    pass


def to_cents(value: str | Decimal) -> int:
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0:
        raise ValueError("Preço inválido.")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_brl(cents: int) -> str:
    whole, fraction = divmod(cents, 100)
    return f"R$ {whole:,}".replace(",", ".") + f",{fraction:02d}"


def quote(base_cents: int, discounts: list[int], payment_method: str | None = None) -> dict:
    if len(discounts) > 1:
        raise PromotionConflict("Há mais de uma promoção ativa. Confirmar com a loja.")
    discount = discounts[0] if discounts else (5 if payment_method == "pix" else 0)
    if base_cents < 0 or not 0 <= discount <= 100:
        raise ValueError("Valor ou desconto inválido.")
    final = int((Decimal(base_cents) * (100 - discount) / 100).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    ))
    return {
        "original_price": format_brl(base_cents),
        "final_price": format_brl(final),
        "original_cents": base_cents,
        "final_cents": final,
        "discount_percent": discount,
        "discount_origin": "promotion" if discounts else ("pix" if discount else "none"),
        "payment_method": payment_method or "not_specified",
        "pix_cumulative": False,
    }
