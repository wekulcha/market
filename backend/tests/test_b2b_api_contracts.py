from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.deps.b2b import (
    B2BPrincipal,
    require_active_subscription,
    require_admin,
    require_buyer,
    require_seller,
    require_superadmin,
)
from app.models.b2b import InventoryBalance, InventoryReservation
from app.routers.b2b_buyer import (
    CheckoutBody,
    _offer_dto,
    buyer_order,
    create_order,
)
from app.routers.b2b_internal import BuyerRegistrationRequest, register_buyer
from app.routers.b2b_webhooks import payment_webhook
from app.schemas.b2b import BuyerOfferResponse, BuyerOrderItemResponse
from app.services.b2b_orders import expire_reservations, release_order_inventory
from app.services.b2b_payments import PaymentStatus, PaymentWebhookEvent


class _Scalars:
    def __init__(self, values):
        self._values = list(values)

    def first(self):
        return self._values[0] if self._values else None

    def all(self):
        return list(self._values)


class _Result:
    def __init__(self, values=(), *, scalar_one=None):
        self._values = list(values)
        self._scalar_one = scalar_one

    def scalars(self):
        return _Scalars(self._values)

    def scalar_one(self):
        if self._scalar_one is not None:
            return self._scalar_one
        if len(self._values) != 1:
            raise AssertionError("fake result does not contain exactly one scalar")
        return self._values[0]


class _SequenceSession:
    """Small async-session contract double; it never pretends to provide locking."""

    def __init__(self, *, execute_results=(), get_results=()):
        self._execute_results = list(execute_results)
        self._get_results = list(get_results)
        self.added = []
        self.deleted = []

    async def execute(self, _statement):
        if not self._execute_results:
            raise AssertionError("unexpected database execute")
        return self._execute_results.pop(0)

    async def get(self, _model, _identity, **_kwargs):
        if not self._get_results:
            raise AssertionError("unexpected database get")
        return self._get_results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None

    async def delete(self, value):
        self.deleted.append(value)


def _principal(*roles: str, user_id: int = 101) -> B2BPrincipal:
    return B2BPrincipal(
        user=SimpleNamespace(id=user_id, username=f"user-{user_id}"),
        roles=frozenset(roles),
    )


@pytest.mark.asyncio
async def test_role_dependencies_are_fail_closed_and_do_not_cross_grant_roles() -> None:
    buyer = _principal("BUYER")
    seller = _principal("SELLER")
    admin = _principal("ADMIN")
    superadmin = _principal("SUPERADMIN")

    assert await require_buyer(buyer) is buyer
    assert await require_seller(seller) is seller
    assert await require_admin(admin) is admin
    assert await require_admin(superadmin) is superadmin
    assert await require_superadmin(superadmin) is superadmin

    denied = (
        (require_buyer, seller),
        (require_seller, buyer),
        (require_admin, buyer),
        (require_superadmin, admin),
    )
    for dependency, principal in denied:
        with pytest.raises(HTTPException) as exc_info:
            await dependency(principal)
        assert exc_info.value.status_code == 403


def test_buyer_schema_contract_has_no_supplier_cost_margin_or_private_fields() -> None:
    forbidden = {
        "supplier_profile_id",
        "seller_profile_id",
        "supplier_unit_price_kopecks",
        "supplier_total_kopecks",
        "markup_type",
        "markup_value",
        "margin_kopecks",
        "supplier_comment",
        "admin_comment",
        "pickup_address",
        "pickup_address_snapshot",
        "legal_details",
        "contact_name",
        "phone",
    }

    assert forbidden.isdisjoint(BuyerOfferResponse.model_fields)
    assert forbidden.isdisjoint(BuyerOrderItemResponse.model_fields)

    offer_schema = BuyerOfferResponse.model_json_schema(by_alias=True)
    item_schema = BuyerOrderItemResponse.model_json_schema(by_alias=True)
    rendered = f"{offer_schema!r} {item_schema!r}".lower()
    for private_name in forbidden:
        assert private_name not in rendered


def test_catalog_projection_does_not_leak_private_orm_attributes() -> None:
    offer = SimpleNamespace(
        id=uuid4(),
        expires_at=None,
        supplier_profile_id=uuid4(),
        admin_comment="internal offer note",
    )
    revision = SimpleNamespace(
        public_title="Публичное название",
        original_title="Внутреннее название",
        public_description="Публичное описание",
        original_description="Внутреннее описание",
        buyer_unit_price_kopecks=12_500,
        supplier_unit_price_kopecks=9_000,
        markup_type="PERCENT",
        markup_value=Decimal("38.8889"),
        supplier_comment="supplier-only note",
        currency="RUB",
        sale_unit="кг",
        package_size=Decimal("1.000"),
        minimum_order_quantity=Decimal("2.000"),
        quantity_step=Decimal("1.000"),
        expiration_date=None,
        storage_conditions="0..+4 C",
    )
    category = SimpleNamespace(name="Овощи")
    balance = SimpleNamespace(available_quantity=Decimal("42.000"))

    dto = _offer_dto((offer, revision, category, balance), ["/safe.jpg"], "FULL")

    assert dto["buyerUnitPriceKopecks"] == 12_500
    assert "supplier" not in repr(dto).lower()
    assert "markup" not in repr(dto).lower()
    assert "admin" not in repr(dto).lower()
    assert "pickup" not in repr(dto).lower()
    assert 9_000 not in dto.values()


@pytest.mark.asyncio
async def test_buyer_order_idor_is_hidden_as_not_found() -> None:
    buyer_profile_id = uuid4()
    foreign_order = SimpleNamespace(id=uuid4(), buyer_profile_id=uuid4())
    db = _SequenceSession(get_results=[foreign_order])

    with patch(
        "app.routers.b2b_buyer.buyer_profile_for",
        AsyncMock(return_value=SimpleNamespace(id=buyer_profile_id)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await buyer_order(foreign_order.id, principal=_principal("BUYER"), db=db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Заказ не найден"


@pytest.mark.asyncio
async def test_buyer_order_projection_omits_supplier_cost_and_pickup_data() -> None:
    now = datetime.now(timezone.utc)
    buyer_profile_id = uuid4()
    order = SimpleNamespace(
        id=uuid4(),
        buyer_profile_id=buyer_profile_id,
        order_number="B2B-TEST-1",
        status="PENDING_CONFIRMATION",
        created_at=now,
        desired_delivery_from=None,
        desired_delivery_to=None,
        delivery_address_snapshot="Публичный адрес покупателя",
        total_kopecks=15_000,
        currency="RUB",
    )
    item = SimpleNamespace(
        id=uuid4(),
        public_title_snapshot="Томаты",
        quantity=Decimal("3.000"),
        sale_unit_snapshot="кг",
        buyer_unit_price_kopecks=5_000,
        buyer_total_kopecks=15_000,
        supplier_unit_price_kopecks=3_000,
        supplier_total_kopecks=9_000,
        margin_kopecks=6_000,
        pickup_address_snapshot="Секретный склад поставщика",
    )
    db = _SequenceSession(
        get_results=[order],
        execute_results=[_Result([item])],
    )

    with patch(
        "app.routers.b2b_buyer.buyer_profile_for",
        AsyncMock(return_value=SimpleNamespace(id=buyer_profile_id)),
    ):
        dto = await buyer_order(order.id, principal=_principal("BUYER"), db=db)

    serialized = repr(dto).lower()
    assert dto["items"][0]["buyerTotalKopecks"] == 15_000
    assert "supplier" not in serialized
    assert "margin" not in serialized
    assert "pickup" not in serialized
    assert "секретный склад" not in serialized
    assert 3_000 not in dto["items"][0].values()


@pytest.mark.asyncio
async def test_subscription_guard_returns_402_without_active_subscription() -> None:
    db = SimpleNamespace()
    with patch(
        "app.deps.b2b.active_subscription_for",
        AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await require_active_subscription(db, uuid4())
    assert exc_info.value.status_code == 402

    subscription = SimpleNamespace(id=uuid4(), status="ACTIVE")
    with patch(
        "app.deps.b2b.active_subscription_for",
        AsyncMock(return_value=subscription),
    ):
        assert await require_active_subscription(db, uuid4()) is subscription


@pytest.mark.asyncio
async def test_checkout_replays_existing_order_before_touching_cart_or_inventory() -> None:
    buyer_profile_id = uuid4()
    existing = SimpleNamespace(
        id=uuid4(),
        buyer_profile_id=buyer_profile_id,
        order_number="B2B-IDEMPOTENT",
        status="PENDING_CONFIRMATION",
        created_at=datetime.now(timezone.utc),
        desired_delivery_from=None,
        desired_delivery_to=None,
        delivery_address_snapshot="Москва",
        total_kopecks=10_000,
        currency="RUB",
    )
    db = _SequenceSession(
        execute_results=[_Result([existing]), _Result(scalar_one=2)],
    )
    key = "checkout-contract-001"
    body = CheckoutBody(
        addressId=uuid4(),
        recipientName="Покупатель",
        recipientPhone="+79990000000",
        paymentMethod="PAY_ON_DELIVERY",
        idempotencyKey=key,
        termsAccepted=True,
    )

    with (
        patch(
            "app.routers.b2b_buyer.buyer_profile_for",
            AsyncMock(return_value=SimpleNamespace(id=buyer_profile_id)),
        ),
        patch(
            "app.routers.b2b_buyer.require_active_subscription",
            AsyncMock(return_value=SimpleNamespace(status="ACTIVE")),
        ),
    ):
        first = await create_order(
            body,
            SimpleNamespace(state=SimpleNamespace()),
            principal=_principal("BUYER"),
            db=db,
            idempotency_header=key,
        )

    assert first["id"] == str(existing.id)
    assert first["itemsCount"] == 2
    assert not db.added


@pytest.mark.asyncio
async def test_checkout_rejects_conflicting_header_and_body_idempotency_keys() -> None:
    body = CheckoutBody(
        addressId=uuid4(),
        recipientName="Покупатель",
        recipientPhone="+79990000000",
        idempotencyKey="checkout-body-001",
        termsAccepted=True,
    )
    with (
        patch(
            "app.routers.b2b_buyer.buyer_profile_for",
            AsyncMock(return_value=SimpleNamespace(id=uuid4())),
        ),
        patch(
            "app.routers.b2b_buyer.require_active_subscription",
            AsyncMock(return_value=SimpleNamespace(status="ACTIVE")),
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_order(
                body,
                SimpleNamespace(state=SimpleNamespace()),
                principal=_principal("BUYER"),
                db=_SequenceSession(),
                idempotency_header="checkout-header-001",
            )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_single_use_invite_replay_is_idempotent_only_for_same_telegram_user() -> None:
    now = datetime.now(timezone.utc)
    telegram_id = 777001
    user = SimpleNamespace(id=telegram_id, phone="+79990000001")
    profile = SimpleNamespace(id=uuid4(), user_id=telegram_id, status="REGISTERED", phone=user.phone)
    invite = SimpleNamespace(
        id=uuid4(),
        status="EXHAUSTED",
        expires_at=now + timedelta(days=1),
        bound_telegram_user_id=telegram_id,
        activated_by_user_id=telegram_id,
        use_count=1,
        max_uses=1,
        trial_days=0,
        plan_id=None,
        last_used_at=now,
    )
    db = _SequenceSession(execute_results=[_Result([invite]), _Result([profile])])
    body = BuyerRegistrationRequest(
        telegramId=telegram_id,
        username="same-user",
        phone="+79990000001",
        inviteToken="a" * 32,
    )

    with (
        patch("app.routers.b2b_internal._assert_internal_secret"),
        patch("app.routers.b2b_internal._register_user", AsyncMock(return_value=user)),
        patch("app.routers.b2b_internal._grant_role", AsyncMock()),
        patch("app.routers.b2b_internal._upsert_account", AsyncMock()),
    ):
        replay = await register_buyer(
            body,
            SimpleNamespace(state=SimpleNamespace(request_id="test")),
            db=db,
            internal_secret="test-secret",
        )

    assert replay["repeated"] is True
    assert invite.use_count == 1

    foreign_body = BuyerRegistrationRequest(
        telegramId=telegram_id + 1,
        username="foreign-user",
        phone="+79990000002",
        inviteToken="a" * 32,
    )
    foreign_db = _SequenceSession(execute_results=[_Result([invite])])
    with patch("app.routers.b2b_internal._assert_internal_secret"):
        with pytest.raises(HTTPException) as exc_info:
            await register_buyer(
                foreign_body,
                SimpleNamespace(state=SimpleNamespace(request_id="test")),
                db=foreign_db,
                internal_secret="test-secret",
            )
    assert exc_info.value.status_code == 409
    assert invite.use_count == 1


@pytest.mark.asyncio
async def test_webhook_replay_returns_duplicate_without_reapplying_payment() -> None:
    stored = SimpleNamespace(status="PROCESSED")
    db = _SequenceSession(execute_results=[_Result([stored])])
    parsed = PaymentWebhookEvent(
        provider="mock",
        event_id="evt-replay-001",
        provider_payment_id="pay-001",
        status=PaymentStatus.PAID,
        amount_kopecks=15_000,
        currency="RUB",
        raw_payload={"event_id": "evt-replay-001"},
    )
    provider = SimpleNamespace(parse_webhook=lambda _payload, _signature: parsed)
    request = SimpleNamespace(body=AsyncMock(return_value=b"{}"))

    with (
        patch("app.routers.b2b_webhooks._provider", return_value=provider),
        patch(
            "app.routers.b2b_webhooks.activate_paid_subscription",
            AsyncMock(side_effect=AssertionError("replay must not reactivate subscription")),
        ),
        patch(
            "app.routers.b2b_webhooks.enqueue_notification",
            AsyncMock(side_effect=AssertionError("replay must not enqueue notification")),
        ),
    ):
        response = await payment_webhook(
            "mock",
            request,
            db=db,
            signature="test-signature",
        )

    assert response == {"status": "processed", "duplicate": True}
    assert not db.added


@pytest.mark.asyncio
async def test_release_and_expiry_contracts_update_reservation_and_balance_once() -> None:
    now = datetime.now(timezone.utc)
    order = SimpleNamespace(
        id=uuid4(),
        order_number="B2B-EXPIRY-1",
        status="PENDING_CONFIRMATION",
        canceled_at=None,
    )
    balance = InventoryBalance(
        id=uuid4(),
        offer_id=uuid4(),
        total_quantity=Decimal("10.000"),
        reserved_quantity=Decimal("4.000"),
        sold_quantity=Decimal("0.000"),
        version=1,
    )
    reservation = InventoryReservation(
        id=uuid4(),
        inventory_balance_id=balance.id,
        buyer_profile_id=uuid4(),
        order_id=order.id,
        quantity=Decimal("4.000"),
        status="ACTIVE",
        idempotency_key="reservation-contract-001",
        expires_at=now - timedelta(seconds=1),
    )
    db = _SequenceSession(get_results=[balance])

    with patch(
        "app.services.b2b_orders._locked_reservations",
        AsyncMock(return_value=[reservation]),
    ):
        await release_order_inventory(
            db,
            order,
            reason="Buyer canceled",
            actor_user_id=101,
        )

    assert reservation.status == "RELEASED"
    assert balance.reserved_quantity == Decimal("0.000")
    assert balance.sold_quantity == Decimal("0.000")
    assert balance.version == 2
    movements = [value for value in db.added if value.__class__.__name__ == "InventoryMovement"]
    assert len(movements) == 1
    assert movements[0].movement_type == "RELEASE"

    expiring_order = SimpleNamespace(
        id=uuid4(),
        order_number="B2B-EXPIRY-2",
        buyer_profile_id=uuid4(),
        status="PENDING_CONFIRMATION",
        canceled_at=None,
    )
    expiry_db = _SequenceSession(
        execute_results=[_Result([expiring_order]), _Result([])],
        get_results=[None],
    )
    release = AsyncMock()
    with patch("app.services.b2b_orders.release_order_inventory", release):
        count = await expire_reservations(expiry_db, now=now)

    assert count == 1
    assert expiring_order.status == "CANCELED"
    assert expiring_order.canceled_at == now
    release.assert_awaited_once()
    histories = [
        value for value in expiry_db.added if value.__class__.__name__ == "B2BOrderStatusHistory"
    ]
    assert len(histories) == 1
    assert histories[0].to_status == "CANCELED"
