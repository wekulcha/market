from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum


class PricingError(ValueError):
    """Raised when a B2B price cannot be calculated safely."""


class MarkupType(str, Enum):
    PERCENT = "PERCENT"
    FIXED = "FIXED"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class PriceSnapshot:
    supplier_unit_price_kopecks: int
    markup_type: MarkupType
    markup_value: Decimal
    buyer_unit_price_kopecks: int
    margin_kopecks: int


def _money(value: int, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PricingError(f"{field} must be an integer number of kopecks")
    if value < 0:
        raise PricingError(f"{field} cannot be negative")
    return value


def _decimal(value: Decimal | int | str, *, field: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise PricingError(f"{field} must not be a boolean or float")
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PricingError(f"{field} is not a valid decimal") from exc
    if not result.is_finite():
        raise PricingError(f"{field} must be finite")
    return result


def _integer_kopecks(value: Decimal | int | str, *, field: str) -> int:
    decimal_value = _decimal(value, field=field)
    rounded = decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if decimal_value != rounded:
        raise PricingError(f"{field} must be a whole number of kopecks")
    return _money(int(rounded), field=field)


def calculate_buyer_unit_price(
    supplier_unit_price_kopecks: int,
    markup_type: MarkupType | str,
    markup_value: Decimal | int | str,
) -> int:
    """Calculate a buyer price using deterministic half-up rounding.

    ``PERCENT`` uses a percent value (``15`` means 15%). ``FIXED`` uses an
    integer number of kopecks added to the supplier price. ``MANUAL`` treats
    the value as the final buyer price in kopecks. Negative margins are not
    allowed by this domain helper.
    """

    supplier_price = _money(
        supplier_unit_price_kopecks,
        field="supplier_unit_price_kopecks",
    )
    try:
        kind = MarkupType(markup_type)
    except ValueError as exc:
        raise PricingError(f"unsupported markup type: {markup_type}") from exc

    value = _decimal(markup_value, field="markup_value")
    if value < 0:
        raise PricingError("markup_value cannot be negative")

    if kind is MarkupType.PERCENT:
        increment = (
            Decimal(supplier_price) * value / Decimal("100")
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        buyer_price = supplier_price + int(increment)
    elif kind is MarkupType.FIXED:
        buyer_price = supplier_price + _integer_kopecks(value, field="markup_value")
    else:
        buyer_price = _integer_kopecks(value, field="markup_value")
        if buyer_price < supplier_price:
            raise PricingError("manual buyer price cannot be below supplier price")

    return _money(buyer_price, field="buyer_unit_price_kopecks")


def build_price_snapshot(
    supplier_unit_price_kopecks: int,
    markup_type: MarkupType | str,
    markup_value: Decimal | int | str,
) -> PriceSnapshot:
    kind = MarkupType(markup_type)
    value = _decimal(markup_value, field="markup_value")
    buyer_price = calculate_buyer_unit_price(
        supplier_unit_price_kopecks,
        kind,
        value,
    )
    return PriceSnapshot(
        supplier_unit_price_kopecks=supplier_unit_price_kopecks,
        markup_type=kind,
        markup_value=value,
        buyer_unit_price_kopecks=buyer_price,
        margin_kopecks=buyer_price - supplier_unit_price_kopecks,
    )


def calculate_line_total_kopecks(unit_price_kopecks: int, quantity: Decimal | int | str) -> int:
    unit_price = _money(unit_price_kopecks, field="unit_price_kopecks")
    qty = _decimal(quantity, field="quantity")
    if qty <= 0:
        raise PricingError("quantity must be greater than zero")
    return int(
        (Decimal(unit_price) * qty).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
