from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.b2b import BuyerProfile, SubscriptionPayment, WebhookEvent
from app.services.b2b_common import utcnow
from app.services.b2b_metrics import PAYMENT_WEBHOOKS
from app.services.b2b_notifications import enqueue_notification
from app.services.b2b_payments import (
    MockPaymentProvider,
    PaymentError,
    PaymentStatus,
    payload_sha256,
)
from app.services.b2b_rate_limit import rate_limit
from app.services.b2b_subscriptions import activate_paid_subscription


router = APIRouter(prefix="/webhooks", tags=["b2b-webhooks"])


def _provider(name: str):
    settings = get_settings()
    if name != settings.payment_provider:
        raise HTTPException(404, "Payment provider not configured")
    if name == "mock":
        try:
            return MockPaymentProvider(
                environment=settings.app_env,
                webhook_secret=settings.payment_webhook_secret,
            )
        except (PaymentError, RuntimeError) as exc:
            raise HTTPException(503, str(exc)) from exc
    raise HTTPException(501, "Payment provider adapter is not implemented")


@router.post(
    "/payments/{provider_name}",
    dependencies=[Depends(rate_limit("payment-webhook", requests=120, seconds=60))],
)
async def payment_webhook(
    provider_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    signature: str | None = Header(None, alias="X-Payment-Signature"),
):
    payload = await request.body()
    if len(payload) > 1_000_000:
        raise HTTPException(413, "Webhook payload too large")
    provider = _provider(provider_name)
    try:
        parsed = provider.parse_webhook(payload, signature or "")
    except PaymentError as exc:
        PAYMENT_WEBHOOKS.labels(provider_name, "rejected").inc()
        raise HTTPException(401, str(exc)) from exc

    existing = (
        await db.execute(
            select(WebhookEvent).where(
                WebhookEvent.provider == provider_name,
                WebhookEvent.external_event_id == parsed.event_id,
            )
        )
    ).scalars().first()
    if existing:
        PAYMENT_WEBHOOKS.labels(provider_name, "duplicate").inc()
        return {"status": existing.status.lower(), "duplicate": True}

    event = WebhookEvent(
        provider=provider_name,
        external_event_id=parsed.event_id,
        payload_hash=payload_sha256(payload),
        payload=dict(parsed.raw_payload),
        signature_valid=True,
        status="RECEIVED",
    )
    db.add(event)
    await db.flush()
    payment = (
        await db.execute(
            select(SubscriptionPayment)
            .where(
                SubscriptionPayment.provider == provider_name,
                SubscriptionPayment.provider_payment_id == parsed.provider_payment_id,
            )
            .with_for_update()
        )
    ).scalars().first()
    if not payment:
        event.status = "FAILED"
        event.error = "Payment not found"
        PAYMENT_WEBHOOKS.labels(provider_name, "payment_not_found").inc()
        return JSONResponse(status_code=202, content={"status": "payment_not_found"})
    if parsed.amount_kopecks is not None and parsed.amount_kopecks != payment.amount_kopecks:
        event.status = "FAILED"
        event.error = "Payment amount mismatch"
        PAYMENT_WEBHOOKS.labels(provider_name, "amount_mismatch").inc()
        return JSONResponse(status_code=400, content={"status": "amount_mismatch"})
    if parsed.currency is not None and parsed.currency != payment.currency:
        event.status = "FAILED"
        event.error = "Payment currency mismatch"
        PAYMENT_WEBHOOKS.labels(provider_name, "currency_mismatch").inc()
        return JSONResponse(status_code=400, content={"status": "currency_mismatch"})

    if parsed.status is PaymentStatus.PAID:
        subscription = await activate_paid_subscription(db, payment)
        message = f"Подписка успешно оплачена и действует до {subscription.ends_at:%d.%m.%Y}."
    else:
        payment.status = parsed.status.value
        now = utcnow()
        if parsed.status is PaymentStatus.FAILED:
            payment.failed_at = now
        elif parsed.status is PaymentStatus.REFUNDED:
            payment.refunded_at = now
        message = f"Статус платежа за подписку: {parsed.status.value}."
    buyer = await db.get(BuyerProfile, payment.buyer_profile_id)
    if buyer:
        await enqueue_notification(
            db,
            user_id=buyer.user_id,
            recipient=buyer.user_id,
            event_type=f"SUBSCRIPTION_PAYMENT_{parsed.status.value}",
            idempotency_key=f"payment-status:{payment.id}:{parsed.status.value}",
            text=message,
            bot_scope="BUYER",
            deep_link=f"{get_settings().public_base_url.rstrip('/')}{get_settings().buyer_app_path}/subscription",
        )
    event.status = "PROCESSED"
    event.processed_at = utcnow()
    PAYMENT_WEBHOOKS.labels(provider_name, parsed.status.value.lower()).inc()
    return {"status": "processed", "duplicate": False}
