from __future__ import annotations

from enum import Enum


class InvalidOrderTransition(ValueError):
    pass


class OrderStatus(str, Enum):
    DRAFT = "DRAFT"
    RESERVED = "RESERVED"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    SELLER_PREPARING = "SELLER_PREPARING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    COURIER_ASSIGNED = "COURIER_ASSIGNED"
    PICKED_UP = "PICKED_UP"
    IN_DELIVERY = "IN_DELIVERY"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    REFUNDED = "REFUNDED"


ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.DRAFT: frozenset({OrderStatus.RESERVED, OrderStatus.CANCELED}),
    OrderStatus.RESERVED: frozenset(
        {OrderStatus.PENDING_CONFIRMATION, OrderStatus.CANCELED}
    ),
    OrderStatus.PENDING_CONFIRMATION: frozenset(
        {OrderStatus.CONFIRMED, OrderStatus.CANCELED}
    ),
    OrderStatus.CONFIRMED: frozenset(
        {OrderStatus.SELLER_PREPARING, OrderStatus.CANCELED}
    ),
    OrderStatus.SELLER_PREPARING: frozenset(
        {OrderStatus.READY_FOR_PICKUP, OrderStatus.CANCELED}
    ),
    OrderStatus.READY_FOR_PICKUP: frozenset(
        {OrderStatus.COURIER_ASSIGNED, OrderStatus.CANCELED}
    ),
    OrderStatus.COURIER_ASSIGNED: frozenset(
        {OrderStatus.PICKED_UP, OrderStatus.CANCELED}
    ),
    OrderStatus.PICKED_UP: frozenset({OrderStatus.IN_DELIVERY}),
    OrderStatus.IN_DELIVERY: frozenset({OrderStatus.DELIVERED}),
    OrderStatus.DELIVERED: frozenset(
        {OrderStatus.COMPLETED, OrderStatus.REFUNDED}
    ),
    OrderStatus.COMPLETED: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.CANCELED: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.REFUNDED: frozenset(),
}


def allowed_order_transitions(status: OrderStatus | str) -> frozenset[OrderStatus]:
    try:
        current = OrderStatus(status)
    except ValueError as exc:
        raise InvalidOrderTransition(f"unknown order status: {status}") from exc
    return ORDER_TRANSITIONS[current]


def can_transition_order(
    current_status: OrderStatus | str,
    target_status: OrderStatus | str,
    *,
    allow_same: bool = False,
) -> bool:
    try:
        current = OrderStatus(current_status)
        target = OrderStatus(target_status)
    except ValueError:
        return False
    if current == target:
        return allow_same
    return target in ORDER_TRANSITIONS[current]


def validate_order_transition(
    current_status: OrderStatus | str,
    target_status: OrderStatus | str,
    *,
    allow_same: bool = False,
) -> OrderStatus:
    try:
        current = OrderStatus(current_status)
        target = OrderStatus(target_status)
    except ValueError as exc:
        raise InvalidOrderTransition("unknown order status") from exc
    if not can_transition_order(current, target, allow_same=allow_same):
        raise InvalidOrderTransition(
            f"order transition {current.value} -> {target.value} is not allowed"
        )
    return target


def is_terminal_order_status(status: OrderStatus | str) -> bool:
    current = OrderStatus(status)
    return not ORDER_TRANSITIONS[current]
