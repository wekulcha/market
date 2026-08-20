"""PostgreSQL-only B2B integration tests.

These tests deliberately do not fall back to SQLite or mocked sessions: the
locking and uniqueness claims below only mean something on PostgreSQL. Set
``B2B_TEST_DATABASE_URL`` to an asyncpg URL for a disposable test database.
Every test gets a random schema which is dropped afterwards.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401 - registers every FK target in Base.metadata
from app.database import Base
from app.deps.b2b import B2BPrincipal, require_active_subscription
from app.models.b2b import (
    B2BCategory,
    B2BOrder,
    B2BOrderStatusHistory,
    BuyerAddress,
    BuyerProfile,
    Cart,
    CartItem,
    InventoryBalance,
    InventoryMovement,
    InventoryReservation,
    InviteLink,
    Offer,
    OfferRevision,
    SellerProfile,
    Subscription,
    SubscriptionPlan,
    WebhookEvent,
)
from app.models.user import User
from app.routers.b2b_buyer import CheckoutBody, create_order
from app.routers.b2b_internal import BuyerRegistrationRequest, register_buyer
from app.routers.b2b_webhooks import payment_webhook
from app.services.b2b_common import hash_secret
from app.services.b2b_orders import expire_reservations, transition_order
from app.services.b2b_payments import PaymentStatus, PaymentWebhookEvent


POSTGRES_TEST_URL = os.getenv("B2B_TEST_DATABASE_URL", "").strip()

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not POSTGRES_TEST_URL,
        reason=(
            "requires a real disposable PostgreSQL database; set "
            "B2B_TEST_DATABASE_URL=postgresql+asyncpg://..."
        ),
    ),
]


@asynccontextmanager
async def _isolated_postgres():
    if not POSTGRES_TEST_URL.startswith("postgresql+asyncpg://"):
        pytest.skip("B2B_TEST_DATABASE_URL must use the postgresql+asyncpg driver")

    schema = f"b2b_it_{uuid4().hex}"
    bootstrap = create_async_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    engine = None
    try:
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        engine = create_async_engine(
            POSTGRES_TEST_URL,
            pool_pre_ping=True,
            connect_args={"server_settings": {"search_path": f"{schema},public"}},
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            async with bootstrap.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            await bootstrap.dispose()


def _user(telegram_id: int, phone: str) -> User:
    return User(
        id=telegram_id,
        username=f"tg_{telegram_id}",
        phone=phone,
        registered_at=datetime.now(),
        is_active=True,
    )


async def _seed_plan(session) -> SubscriptionPlan:
    plan = SubscriptionPlan(
        code=f"test-{uuid4().hex[:10]}",
        name="Integration plan",
        price_kopecks=50_000,
        currency="RUB",
        duration_days=30,
        trial_days=0,
        is_active=True,
    )
    session.add(plan)
    await session.flush()
    return plan


async def _seed_buyer(
    session,
    *,
    telegram_id: int,
    phone: str,
    plan: SubscriptionPlan,
    subscription_active: bool = True,
) -> tuple[User, BuyerProfile]:
    user = _user(telegram_id, phone)
    session.add(user)
    await session.flush()
    profile = BuyerProfile(
        user_id=user.id,
        status="ACTIVE" if subscription_active else "REGISTERED",
        company_name=f"Buyer {telegram_id}",
        contact_name=user.username,
        phone=phone,
    )
    session.add(profile)
    await session.flush()
    now = datetime.now(timezone.utc)
    session.add(
        Subscription(
            buyer_profile_id=profile.id,
            plan_id=plan.id,
            status="ACTIVE" if subscription_active else "EXPIRED",
            starts_at=now - timedelta(days=31),
            ends_at=(now + timedelta(days=1) if subscription_active else now - timedelta(days=1)),
            source="TEST",
        )
    )
    await session.flush()
    return user, profile


async def _seed_seller_offer(session, *, total_quantity: Decimal):
    seller_user = _user(900_001, "+79999000001")
    session.add(seller_user)
    await session.flush()
    seller = SellerProfile(
        user_id=seller_user.id,
        status="VERIFIED",
        company_name="Integration supplier",
        contact_name="Supplier",
        phone=seller_user.phone,
        pickup_address="Integration warehouse",
    )
    category = B2BCategory(
        slug=f"integration-{uuid4().hex[:10]}",
        name="Integration category",
        sort_order=1,
        is_active=True,
    )
    session.add_all([seller, category])
    await session.flush()
    offer = Offer(
        seller_profile_id=seller.id,
        status="PUBLISHED",
        published_at=datetime.now(timezone.utc),
        version=1,
    )
    session.add(offer)
    await session.flush()
    revision = OfferRevision(
        offer_id=offer.id,
        revision_number=1,
        category_id=category.id,
        original_title="Integration tomatoes",
        original_description="PostgreSQL integration stock",
        public_title="Томаты",
        public_description="Тестовая партия",
        supplier_unit_price_kopecks=10_000,
        markup_type="FIXED",
        markup_value=Decimal("2.0000"),
        buyer_unit_price_kopecks=12_000,
        currency="RUB",
        sale_unit="кг",
        package_size=Decimal("1.000"),
        proposed_total_quantity=total_quantity,
        minimum_order_quantity=Decimal("1.000"),
        quantity_step=Decimal("1.000"),
        pickup_address=seller.pickup_address,
        is_published=True,
        published_at=datetime.now(timezone.utc),
    )
    balance = InventoryBalance(
        offer_id=offer.id,
        total_quantity=total_quantity,
        reserved_quantity=Decimal("0.000"),
        sold_quantity=Decimal("0.000"),
        version=1,
    )
    session.add_all([revision, balance])
    await session.flush()
    return seller, offer, revision, balance


async def _seed_cart(
    session,
    *,
    profile: BuyerProfile,
    offer: Offer,
    quantity: Decimal,
) -> tuple[BuyerAddress, Cart]:
    address = BuyerAddress(
        buyer_profile_id=profile.id,
        label="Склад",
        address=f"Москва, тестовый адрес {profile.user_id}",
        is_default=True,
        is_active=True,
    )
    cart = Cart(buyer_profile_id=profile.id, status="ACTIVE")
    session.add_all([address, cart])
    await session.flush()
    session.add(CartItem(cart_id=cart.id, offer_id=offer.id, quantity=quantity))
    await session.flush()
    return address, cart


def _principal(user: User) -> B2BPrincipal:
    return B2BPrincipal(user=user, roles=frozenset({"BUYER"}))


def _checkout_body(address_id, key: str, phone: str) -> CheckoutBody:
    return CheckoutBody(
        addressId=address_id,
        recipientName="Integration buyer",
        recipientPhone=phone,
        paymentMethod="PAY_ON_DELIVERY",
        idempotencyKey=key,
        termsAccepted=True,
    )


async def test_postgres_single_use_invite_allows_same_user_replay_but_rejects_reuse() -> None:
    async with _isolated_postgres() as sessions:
        invite_value = "integration-invite-value-000000000001"
        async with sessions() as session:
            invite = InviteLink(
                token_hash=hash_secret(invite_value),
                status="ACTIVE",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                max_uses=1,
                use_count=0,
                trial_days=0,
                source="TEST",
            )
            session.add(invite)
            await session.commit()
            invite_id = invite.id

        body = BuyerRegistrationRequest(
            telegramId=701_001,
            username="invite-owner",
            phone="+79997010001",
            inviteToken=invite_value,
        )
        request = SimpleNamespace(state=SimpleNamespace(request_id="postgres-invite"))
        with patch("app.routers.b2b_internal._assert_internal_secret"):
            async with sessions() as session:
                first = await register_buyer(
                    body,
                    request,
                    db=session,
                    internal_secret="test",
                )
                await session.commit()
            async with sessions() as session:
                replay = await register_buyer(
                    body,
                    request,
                    db=session,
                    internal_secret="test",
                )
                await session.commit()

            foreign = BuyerRegistrationRequest(
                telegramId=701_002,
                username="invite-thief",
                phone="+79997010002",
                inviteToken=invite_value,
            )
            async with sessions() as session:
                with pytest.raises(HTTPException) as exc_info:
                    await register_buyer(
                        foreign,
                        request,
                        db=session,
                        internal_secret="test",
                    )
                await session.rollback()

        async with sessions() as session:
            stored = await session.get(InviteLink, invite_id)
            assert stored is not None
            assert stored.status == "EXHAUSTED"
            assert stored.use_count == 1
            assert stored.bound_telegram_user_id == body.telegramId
        assert first["repeated"] is False
        assert replay["repeated"] is True
        assert exc_info.value.status_code == 409


async def test_postgres_subscription_guard_uses_database_expiry() -> None:
    async with _isolated_postgres() as sessions:
        async with sessions() as session:
            plan = await _seed_plan(session)
            _, profile = await _seed_buyer(
                session,
                telegram_id=702_001,
                phone="+79997020001",
                plan=plan,
                subscription_active=False,
            )
            await session.commit()
            profile_id = profile.id

        async with sessions() as session:
            with pytest.raises(HTTPException) as exc_info:
                await require_active_subscription(session, profile_id)
            assert exc_info.value.status_code == 402

            now = datetime.now(timezone.utc)
            session.add(
                Subscription(
                    buyer_profile_id=profile_id,
                    plan_id=plan.id,
                    status="ACTIVE",
                    starts_at=now,
                    ends_at=now + timedelta(days=30),
                    source="TEST",
                )
            )
            await session.commit()

        async with sessions() as session:
            active = await require_active_subscription(session, profile_id)
            assert active.status == "ACTIVE"


async def test_postgres_webhook_replay_is_a_noop_after_first_event() -> None:
    async with _isolated_postgres() as sessions:
        external_id = "evt-postgres-replay-001"
        async with sessions() as session:
            session.add(
                WebhookEvent(
                    provider="mock",
                    external_event_id=external_id,
                    payload_hash="a" * 64,
                    payload={"event_id": external_id},
                    signature_valid=True,
                    status="PROCESSED",
                    processed_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        parsed = PaymentWebhookEvent(
            provider="mock",
            event_id=external_id,
            provider_payment_id="pay-already-processed",
            status=PaymentStatus.PAID,
            amount_kopecks=50_000,
            currency="RUB",
            raw_payload={"event_id": external_id},
        )
        provider = SimpleNamespace(parse_webhook=lambda _body, _signature: parsed)
        async def body():
            return b"{}"

        request = SimpleNamespace(body=body)
        async with sessions() as session:
            with patch("app.routers.b2b_webhooks._provider", return_value=provider):
                response = await payment_webhook(
                    "mock",
                    request,
                    db=session,
                    signature="already-verified-by-test-provider",
                )
            await session.commit()

        async with sessions() as session:
            count = int(
                (
                    await session.execute(
                        select(func.count(WebhookEvent.id)).where(
                            WebhookEvent.provider == "mock",
                            WebhookEvent.external_event_id == external_id,
                        )
                    )
                ).scalar_one()
            )
        assert response == {"status": "processed", "duplicate": True}
        assert count == 1


async def test_postgres_checkout_idempotency_and_row_lock_prevent_oversell() -> None:
    async with _isolated_postgres() as sessions:
        async with sessions() as session:
            plan = await _seed_plan(session)
            _, offer, _, balance = await _seed_seller_offer(
                session,
                total_quantity=Decimal("5.000"),
            )
            first_user, first_profile = await _seed_buyer(
                session,
                telegram_id=703_001,
                phone="+79997030001",
                plan=plan,
            )
            second_user, second_profile = await _seed_buyer(
                session,
                telegram_id=703_002,
                phone="+79997030002",
                plan=plan,
            )
            first_address, _ = await _seed_cart(
                session,
                profile=first_profile,
                offer=offer,
                quantity=Decimal("4.000"),
            )
            second_address, _ = await _seed_cart(
                session,
                profile=second_profile,
                offer=offer,
                quantity=Decimal("4.000"),
            )
            await session.commit()
            balance_id = balance.id

        async def checkout(user, address, key):
            async with sessions() as session:
                try:
                    result = await create_order(
                        _checkout_body(address.id, key, user.phone),
                        SimpleNamespace(state=SimpleNamespace()),
                        principal=_principal(user),
                        db=session,
                        idempotency_header=key,
                    )
                    await session.commit()
                    return result
                except Exception as exc:
                    await session.rollback()
                    return exc

        first_result, second_result = await asyncio.gather(
            checkout(first_user, first_address, "postgres-checkout-001"),
            checkout(second_user, second_address, "postgres-checkout-002"),
        )
        outcomes = (first_result, second_result)
        successes = [value for value in outcomes if isinstance(value, dict)]
        conflicts = [
            value
            for value in outcomes
            if isinstance(value, HTTPException) and value.status_code == 409
        ]
        assert len(successes) == 1
        assert len(conflicts) == 1

        async with sessions() as session:
            stored_balance = await session.get(InventoryBalance, balance_id)
            assert stored_balance is not None
            assert stored_balance.reserved_quantity == Decimal("4.000")
            assert stored_balance.available_quantity == Decimal("1.000")
            order_count = int((await session.execute(select(func.count(B2BOrder.id)))).scalar_one())
            reservation_count = int(
                (
                    await session.execute(
                        select(func.count(InventoryReservation.id)).where(
                            InventoryReservation.status == "ACTIVE"
                        )
                    )
                ).scalar_one()
            )
            assert order_count == 1
            assert reservation_count == 1

        winning_key = (
            "postgres-checkout-001"
            if first_result in successes
            else "postgres-checkout-002"
        )
        winning_user = first_user if first_result in successes else second_user
        winning_address = first_address if first_result in successes else second_address
        async with sessions() as session:
            replay = await create_order(
                _checkout_body(winning_address.id, winning_key, winning_user.phone),
                SimpleNamespace(state=SimpleNamespace()),
                principal=_principal(winning_user),
                db=session,
                idempotency_header=winning_key,
            )
            await session.commit()
        assert replay["id"] == successes[0]["id"]

        async with sessions() as session:
            assert int((await session.execute(select(func.count(B2BOrder.id)))).scalar_one()) == 1


async def test_postgres_expiry_and_buyer_cancel_release_inventory_with_ledger() -> None:
    async with _isolated_postgres() as sessions:
        async with sessions() as session:
            plan = await _seed_plan(session)
            buyer_user, buyer = await _seed_buyer(
                session,
                telegram_id=704_001,
                phone="+79997040001",
                plan=plan,
            )
            _, offer, _, balance = await _seed_seller_offer(
                session,
                total_quantity=Decimal("10.000"),
            )
            expired_order = B2BOrder(
                order_number="B2B-POSTGRES-EXPIRY",
                buyer_profile_id=buyer.id,
                status="PENDING_CONFIRMATION",
                payment_method="PAY_ON_DELIVERY",
                idempotency_key="postgres-expiry-order-001",
                delivery_address_snapshot="Москва",
                recipient_name="Buyer",
                recipient_phone=buyer_user.phone,
                items_total_kopecks=36_000,
                delivery_fee_kopecks=0,
                total_kopecks=36_000,
                currency="RUB",
                reserved_until=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
            session.add(expired_order)
            await session.flush()
            expired_reservation = InventoryReservation(
                inventory_balance_id=balance.id,
                buyer_profile_id=buyer.id,
                order_id=expired_order.id,
                quantity=Decimal("3.000"),
                status="ACTIVE",
                idempotency_key="postgres-expiry-reservation-001",
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
            balance.reserved_quantity = Decimal("3.000")
            session.add(expired_reservation)
            await session.commit()
            expired_order_id = expired_order.id
            expired_reservation_id = expired_reservation.id
            balance_id = balance.id

        now = datetime.now(timezone.utc)
        async with sessions() as session:
            assert await expire_reservations(session, now=now) == 1
            await session.commit()

        async with sessions() as session:
            order = await session.get(B2BOrder, expired_order_id)
            reservation = await session.get(InventoryReservation, expired_reservation_id)
            stored_balance = await session.get(InventoryBalance, balance_id)
            assert order is not None and order.status == "CANCELED"
            assert reservation is not None and reservation.status == "RELEASED"
            assert stored_balance is not None
            assert stored_balance.reserved_quantity == Decimal("0.000")
            expiry_movements = int(
                (
                    await session.execute(
                        select(func.count(InventoryMovement.id)).where(
                            InventoryMovement.reservation_id == expired_reservation_id,
                            InventoryMovement.movement_type == "RELEASE",
                        )
                    )
                ).scalar_one()
            )
            assert expiry_movements == 1

            cancel_order = B2BOrder(
                order_number="B2B-POSTGRES-CANCEL",
                buyer_profile_id=buyer.id,
                status="PENDING_CONFIRMATION",
                payment_method="PAY_ON_DELIVERY",
                idempotency_key="postgres-cancel-order-001",
                delivery_address_snapshot="Москва",
                recipient_name="Buyer",
                recipient_phone=buyer_user.phone,
                items_total_kopecks=24_000,
                delivery_fee_kopecks=0,
                total_kopecks=24_000,
                currency="RUB",
                reserved_until=now + timedelta(minutes=30),
            )
            session.add(cancel_order)
            await session.flush()
            cancel_reservation = InventoryReservation(
                inventory_balance_id=balance_id,
                buyer_profile_id=buyer.id,
                order_id=cancel_order.id,
                quantity=Decimal("2.000"),
                status="ACTIVE",
                idempotency_key="postgres-cancel-reservation-001",
                expires_at=now + timedelta(minutes=30),
            )
            stored_balance.reserved_quantity = Decimal("2.000")
            session.add(cancel_reservation)
            await session.flush()
            await transition_order(
                session,
                cancel_order,
                "CANCELED",
                actor_user_id=buyer_user.id,
                actor_type="BUYER",
                comment="Buyer canceled in integration test",
            )
            await session.commit()
            cancel_order_id = cancel_order.id
            cancel_reservation_id = cancel_reservation.id

        async with sessions() as session:
            canceled = await session.get(B2BOrder, cancel_order_id)
            reservation = await session.get(InventoryReservation, cancel_reservation_id)
            stored_balance = await session.get(InventoryBalance, balance_id)
            assert canceled is not None and canceled.status == "CANCELED"
            assert reservation is not None and reservation.status == "RELEASED"
            assert stored_balance is not None
            assert stored_balance.reserved_quantity == Decimal("0.000")
            history_count = int(
                (
                    await session.execute(
                        select(func.count(B2BOrderStatusHistory.id)).where(
                            B2BOrderStatusHistory.order_id == cancel_order_id,
                            B2BOrderStatusHistory.to_status == "CANCELED",
                        )
                    )
                ).scalar_one()
            )
            assert history_count == 1
