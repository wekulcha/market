from __future__ import annotations

import json
import unittest
from decimal import Decimal

from app.services.b2b_inventory import (
    InsufficientInventoryError,
    InventoryError,
    InventorySnapshot,
    available_quantity,
    to_quantity,
    validate_order_quantity,
)
from app.services.b2b_payments import (
    MockPaymentProvider,
    PaymentError,
    PaymentRequest,
    PaymentStatus,
    derive_idempotency_key,
    payload_sha256,
    sign_webhook,
    verify_webhook_signature,
)
from app.services.b2b_pricing import (
    MarkupType,
    PricingError,
    build_price_snapshot,
    calculate_buyer_unit_price,
    calculate_line_total_kopecks,
)
from app.services.b2b_state import (
    InvalidOrderTransition,
    OrderStatus,
    allowed_order_transitions,
    can_transition_order,
    is_terminal_order_status,
    validate_order_transition,
)


class PricingTests(unittest.TestCase):
    def test_percent_markup_uses_half_up_kopeck_rounding(self) -> None:
        self.assertEqual(
            calculate_buyer_unit_price(101, MarkupType.PERCENT, Decimal("0.5")),
            102,
        )
        snapshot = build_price_snapshot(10_000, "PERCENT", "12.5")
        self.assertEqual(snapshot.buyer_unit_price_kopecks, 11_250)
        self.assertEqual(snapshot.margin_kopecks, 1_250)

    def test_fixed_and_manual_markup(self) -> None:
        self.assertEqual(calculate_buyer_unit_price(1_000, "FIXED", 125), 1_125)
        self.assertEqual(calculate_buyer_unit_price(1_000, "MANUAL", 1_700), 1_700)

    def test_manual_price_cannot_create_negative_margin(self) -> None:
        with self.assertRaises(PricingError):
            calculate_buyer_unit_price(1_000, "MANUAL", 999)

    def test_money_rejects_float_and_fractional_kopecks(self) -> None:
        with self.assertRaises(PricingError):
            calculate_buyer_unit_price(1_000.0, "PERCENT", "10")  # type: ignore[arg-type]
        with self.assertRaises(PricingError):
            calculate_buyer_unit_price(1_000, "FIXED", Decimal("1.1"))

    def test_line_total_rounds_only_at_money_boundary(self) -> None:
        self.assertEqual(calculate_line_total_kopecks(101, Decimal("1.500")), 152)
        with self.assertRaises(PricingError):
            calculate_line_total_kopecks(101, Decimal("0"))


class InventoryTests(unittest.TestCase):
    def test_quantities_are_exact_to_three_decimal_places(self) -> None:
        self.assertEqual(to_quantity("1.2"), Decimal("1.200"))
        with self.assertRaises(InventoryError):
            to_quantity("1.0001")
        with self.assertRaises(InventoryError):
            to_quantity(float("nan"))

    def test_minimum_and_step_validation(self) -> None:
        self.assertEqual(
            validate_order_quantity("2.500", "1.000", "0.500"),
            Decimal("2.500"),
        )
        with self.assertRaisesRegex(InventoryError, "minimum"):
            validate_order_quantity("0.500", "1.000", "0.500")
        with self.assertRaisesRegex(InventoryError, "step"):
            validate_order_quantity("1.250", "1.000", "0.500")

    def test_available_quantity_rejects_impossible_balance(self) -> None:
        self.assertEqual(
            available_quantity("10", "2.500", "1.000"),
            Decimal("6.500"),
        )
        with self.assertRaises(InventoryError):
            available_quantity("3", "2", "2")

    def test_reserve_release_and_convert_are_immutable(self) -> None:
        initial = InventorySnapshot(Decimal("10.000"))
        reserved = initial.reserve("3.000")
        self.assertEqual(initial.available_quantity, Decimal("10.000"))
        self.assertEqual(reserved.available_quantity, Decimal("7.000"))

        partially_released = reserved.release("1.000")
        sold = partially_released.convert_reservation_to_sale("2.000")
        self.assertEqual(sold.reserved_quantity, Decimal("0.000"))
        self.assertEqual(sold.sold_quantity, Decimal("2.000"))
        self.assertEqual(sold.available_quantity, Decimal("8.000"))

    def test_oversell_and_invalid_adjustment_are_rejected(self) -> None:
        inventory = InventorySnapshot(Decimal("5.000"), Decimal("2.000"), Decimal("1.000"))
        with self.assertRaises(InsufficientInventoryError):
            inventory.reserve("2.001")
        with self.assertRaises(InventoryError):
            inventory.adjust_total("2.999")


class OrderStateTests(unittest.TestCase):
    def test_happy_path_transitions_are_explicit(self) -> None:
        path = [
            OrderStatus.DRAFT,
            OrderStatus.RESERVED,
            OrderStatus.PENDING_CONFIRMATION,
            OrderStatus.CONFIRMED,
            OrderStatus.SELLER_PREPARING,
            OrderStatus.READY_FOR_PICKUP,
            OrderStatus.COURIER_ASSIGNED,
            OrderStatus.PICKED_UP,
            OrderStatus.IN_DELIVERY,
            OrderStatus.DELIVERED,
            OrderStatus.COMPLETED,
        ]
        for current, target in zip(path, path[1:]):
            self.assertTrue(can_transition_order(current, target))
            self.assertEqual(validate_order_transition(current, target), target)

    def test_illegal_skip_and_unknown_status_are_rejected(self) -> None:
        self.assertFalse(can_transition_order("DRAFT", "DELIVERED"))
        self.assertFalse(can_transition_order("UNKNOWN", "DRAFT"))
        with self.assertRaises(InvalidOrderTransition):
            validate_order_transition("DRAFT", "DELIVERED")

    def test_same_state_requires_explicit_opt_in(self) -> None:
        self.assertFalse(can_transition_order("CONFIRMED", "CONFIRMED"))
        self.assertTrue(can_transition_order("CONFIRMED", "CONFIRMED", allow_same=True))

    def test_refunded_is_terminal(self) -> None:
        self.assertTrue(is_terminal_order_status("REFUNDED"))
        self.assertFalse(is_terminal_order_status("COMPLETED"))
        self.assertIn(OrderStatus.REFUNDED, allowed_order_transitions("COMPLETED"))


class PaymentHelperTests(unittest.TestCase):
    def test_mock_provider_is_refused_in_production(self) -> None:
        with self.assertRaises(RuntimeError):
            MockPaymentProvider(environment="production", webhook_secret="secret")

    def test_signature_is_constant_time_verified_and_time_bounded(self) -> None:
        payload = b'{"event_id":"evt-1"}'
        signature = sign_webhook(payload, "secret", timestamp=1_000)
        self.assertTrue(
            verify_webhook_signature(payload, signature, "secret", now=1_100)
        )
        self.assertFalse(
            verify_webhook_signature(payload, signature, "secret", now=1_301)
        )
        self.assertFalse(
            verify_webhook_signature(payload + b" ", signature, "secret", now=1_100)
        )

    def test_hash_and_idempotency_helpers_are_deterministic(self) -> None:
        self.assertEqual(payload_sha256(b"payload"), payload_sha256(b"payload"))
        self.assertEqual(
            derive_idempotency_key("buyer-1", "plan-1"),
            derive_idempotency_key("buyer-1", "plan-1"),
        )
        self.assertNotEqual(
            derive_idempotency_key("buyer-1", "plan-1"),
            derive_idempotency_key("buyer-1", "plan-2"),
        )


class MockPaymentProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.provider = MockPaymentProvider(environment="test", webhook_secret="secret")

    async def test_create_payment_is_idempotent(self) -> None:
        request = PaymentRequest(
            idempotency_key="checkout-123",
            amount_kopecks=12_345,
            currency="rub",
            metadata={"buyer_id": "buyer-1"},
        )
        first = await self.provider.create_payment(request)
        second = await self.provider.create_payment(request)
        self.assertIs(first, second)
        self.assertEqual(first.status, PaymentStatus.PENDING)
        self.assertEqual(first.currency, "RUB")
        self.assertEqual(await self.provider.get_payment(first.provider_payment_id), first)

    async def test_idempotency_key_cannot_be_reused_for_other_amount(self) -> None:
        await self.provider.create_payment(
            PaymentRequest(idempotency_key="checkout-123", amount_kopecks=100)
        )
        with self.assertRaises(PaymentError):
            await self.provider.create_payment(
                PaymentRequest(idempotency_key="checkout-123", amount_kopecks=101)
            )

    async def test_signed_webhook_is_parsed(self) -> None:
        payment = await self.provider.create_payment(
            PaymentRequest(idempotency_key="checkout-123", amount_kopecks=500)
        )
        body = json.dumps(
            {
                "event_id": "evt-123",
                "payment_id": payment.provider_payment_id,
                "status": "paid",
                "amount_kopecks": 500,
                "currency": "rub",
            },
            separators=(",", ":"),
        ).encode()
        signature = sign_webhook(body, "secret", timestamp=1_000)
        event = self.provider.parse_webhook(body, signature, now=1_001)
        self.assertEqual(event.event_id, "evt-123")
        self.assertEqual(event.provider_payment_id, payment.provider_payment_id)
        self.assertEqual(event.status, PaymentStatus.PAID)
        self.assertEqual(event.amount_kopecks, 500)
        self.assertEqual(event.currency, "RUB")

    async def test_bad_webhook_signature_is_rejected(self) -> None:
        with self.assertRaises(PaymentError):
            self.provider.parse_webhook(b"{}", "t=1,v1=bad", now=1)


if __name__ == "__main__":
    unittest.main()
