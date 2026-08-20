from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation


QUANTITY_SCALE = Decimal("0.001")


class InventoryError(ValueError):
    """Base error for inventory invariants."""


class InsufficientInventoryError(InventoryError):
    pass


def to_quantity(value: Decimal | int | str, *, field: str = "quantity") -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise InventoryError(f"{field} must not be a boolean or float")
    try:
        quantity = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InventoryError(f"{field} is not a valid decimal") from exc
    if not quantity.is_finite():
        raise InventoryError(f"{field} must be finite")
    quantized = quantity.quantize(QUANTITY_SCALE)
    if quantity != quantized:
        raise InventoryError(f"{field} supports at most three decimal places")
    return quantized


def validate_order_quantity(
    quantity: Decimal | int | str,
    minimum_quantity: Decimal | int | str,
    quantity_step: Decimal | int | str,
) -> Decimal:
    requested = to_quantity(quantity)
    minimum = to_quantity(minimum_quantity, field="minimum_quantity")
    step = to_quantity(quantity_step, field="quantity_step")
    if requested <= 0:
        raise InventoryError("quantity must be greater than zero")
    if minimum <= 0:
        raise InventoryError("minimum_quantity must be greater than zero")
    if step <= 0:
        raise InventoryError("quantity_step must be greater than zero")
    if requested < minimum:
        raise InventoryError("quantity is below the minimum order quantity")
    if requested % step != 0:
        raise InventoryError("quantity is not aligned to the quantity step")
    return requested


def available_quantity(
    total_quantity: Decimal | int | str,
    reserved_quantity: Decimal | int | str,
    sold_quantity: Decimal | int | str,
) -> Decimal:
    total = to_quantity(total_quantity, field="total_quantity")
    reserved = to_quantity(reserved_quantity, field="reserved_quantity")
    sold = to_quantity(sold_quantity, field="sold_quantity")
    if min(total, reserved, sold) < 0:
        raise InventoryError("inventory quantities cannot be negative")
    available = total - reserved - sold
    if available < 0:
        raise InventoryError("reserved plus sold quantity exceeds total quantity")
    return available


@dataclass(frozen=True)
class InventorySnapshot:
    total_quantity: Decimal
    reserved_quantity: Decimal = Decimal("0.000")
    sold_quantity: Decimal = Decimal("0.000")

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "total_quantity",
            to_quantity(self.total_quantity, field="total_quantity"),
        )
        object.__setattr__(
            self,
            "reserved_quantity",
            to_quantity(self.reserved_quantity, field="reserved_quantity"),
        )
        object.__setattr__(
            self,
            "sold_quantity",
            to_quantity(self.sold_quantity, field="sold_quantity"),
        )
        available_quantity(
            self.total_quantity,
            self.reserved_quantity,
            self.sold_quantity,
        )

    @property
    def available_quantity(self) -> Decimal:
        return available_quantity(
            self.total_quantity,
            self.reserved_quantity,
            self.sold_quantity,
        )

    def reserve(self, quantity: Decimal | int | str) -> InventorySnapshot:
        requested = to_quantity(quantity)
        if requested <= 0:
            raise InventoryError("reservation quantity must be greater than zero")
        if requested > self.available_quantity:
            raise InsufficientInventoryError("not enough available inventory")
        return replace(self, reserved_quantity=self.reserved_quantity + requested)

    def release(self, quantity: Decimal | int | str) -> InventorySnapshot:
        released = to_quantity(quantity)
        if released <= 0:
            raise InventoryError("release quantity must be greater than zero")
        if released > self.reserved_quantity:
            raise InventoryError("cannot release more than the reserved quantity")
        return replace(self, reserved_quantity=self.reserved_quantity - released)

    def convert_reservation_to_sale(
        self,
        quantity: Decimal | int | str,
    ) -> InventorySnapshot:
        sold = to_quantity(quantity)
        if sold <= 0:
            raise InventoryError("sale quantity must be greater than zero")
        if sold > self.reserved_quantity:
            raise InventoryError("cannot sell more than the reserved quantity")
        return replace(
            self,
            reserved_quantity=self.reserved_quantity - sold,
            sold_quantity=self.sold_quantity + sold,
        )

    def adjust_total(self, new_total: Decimal | int | str) -> InventorySnapshot:
        total = to_quantity(new_total, field="new_total")
        if total < self.reserved_quantity + self.sold_quantity:
            raise InventoryError("new total cannot be below reserved plus sold quantity")
        return replace(self, total_quantity=total)
