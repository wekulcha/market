from __future__ import annotations

import asyncio
from datetime import timedelta
from urllib.parse import urlparse

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.b2b import (
    B2BOrder,
    BuyerProfile,
    InventoryReservation,
    Notification,
    Subscription,
)
from app.services.b2b_common import utcnow
from app.services.b2b_metrics import NOTIFICATION_DELIVERIES


async def enqueue_notification(
    db: AsyncSession,
    *,
    user_id: int | None,
    recipient: int | str,
    event_type: str,
    idempotency_key: str,
    text: str,
    bot_scope: str,
    deep_link: str | None = None,
    deep_link_label: str = "Открыть",
    actions: list[dict[str, str]] | None = None,
) -> Notification:
    result = await db.execute(
        select(Notification).where(Notification.idempotency_key == idempotency_key)
    )
    existing = result.scalars().first()
    if existing:
        return existing
    notification = Notification(
        user_id=user_id,
        channel="TELEGRAM",
        event_type=event_type,
        idempotency_key=idempotency_key,
        recipient=str(recipient),
        deep_link=deep_link,
        payload={
            "text": text,
            "botScope": bot_scope.upper(),
            "deepLinkLabel": deep_link_label[:40] or "Открыть",
            "actions": actions or [],
        },
        status="PENDING",
        attempt_count=0,
        max_attempts=get_settings().notification_max_attempts,
        next_attempt_at=utcnow(),
    )
    db.add(notification)
    await db.flush()
    return notification


def _token_for_scope(scope: str) -> str:
    settings = get_settings()
    return {
        "BUYER": settings.b2b_buyer_bot_token,
        "SELLER": settings.b2b_seller_bot_token,
        "ADMIN": settings.b2b_admin_bot_token,
    }.get(scope.upper(), "")


async def _send_telegram(notification: Notification) -> None:
    scope = str(notification.payload.get("botScope") or "").upper()
    token = _token_for_scope(scope)
    if not token:
        raise RuntimeError(f"Telegram token for {scope or 'unknown'} scope is not configured")
    text = str(notification.payload.get("text") or "").strip()
    if not text:
        raise RuntimeError("Notification text is empty")
    body: dict[str, object] = {
        "chat_id": int(notification.recipient),
        "text": text,
        "disable_web_page_preview": True,
    }
    keyboard: list[list[dict[str, object]]] = []
    if notification.deep_link and notification.deep_link.startswith("https://"):
        settings = get_settings()
        public_origin = urlparse(settings.public_base_url)
        target = urlparse(notification.deep_link)
        destination: dict[str, object]
        if (
            target.scheme == "https"
            and target.netloc == public_origin.netloc
            and public_origin.netloc
        ):
            destination = {"web_app": {"url": notification.deep_link}}
        else:
            destination = {"url": notification.deep_link}
        keyboard.append(
            [
                {
                    "text": str(notification.payload.get("deepLinkLabel") or "Открыть")[:40],
                    **destination,
                }
            ]
        )
    action_row = []
    for action in notification.payload.get("actions") or []:
        label = str(action.get("label") or "")[:40]
        callback_data = str(action.get("callbackData") or "")[:64]
        if label and callback_data:
            action_row.append({"text": label, "callback_data": callback_data})
    if action_row:
        keyboard.append(action_row)
    if keyboard:
        body["reply_markup"] = {"inline_keyboard": keyboard}
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=15.0,
        proxy=settings.telegram_proxy_url or None,
    ) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=body,
        )
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(f"Telegram API returned HTTP {response.status_code}")


async def claim_notifications(db: AsyncSession, *, limit: int = 20) -> list[Notification]:
    now = utcnow()
    stale_before = now - timedelta(minutes=5)
    result = await db.execute(
        select(Notification)
        .where(
            or_(
                (
                    Notification.status.in_(("PENDING", "RETRY"))
                    & or_(
                        Notification.next_attempt_at.is_(None),
                        Notification.next_attempt_at <= now,
                    )
                ),
                (
                    (Notification.status == "PROCESSING")
                    & (Notification.updated_at <= stale_before)
                ),
            ),
        )
        .order_by(Notification.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    notifications = list(result.scalars().all())
    for notification in notifications:
        notification.status = "PROCESSING"
        notification.attempt_count += 1
    await db.flush()
    return notifications


async def enqueue_due_reminders(db: AsyncSession) -> int:
    """Persist idempotent reservation/subscription reminders for the worker."""
    now = utcnow()
    reservation_horizon = now + timedelta(minutes=5)
    expiring_orders = list(
        (
            await db.execute(
                select(B2BOrder, BuyerProfile)
                .join(
                    InventoryReservation,
                    InventoryReservation.order_id == B2BOrder.id,
                )
                .join(BuyerProfile, BuyerProfile.id == B2BOrder.buyer_profile_id)
                .where(
                    InventoryReservation.status == "ACTIVE",
                    InventoryReservation.expires_at > now,
                    InventoryReservation.expires_at <= reservation_horizon,
                    B2BOrder.status.in_(("RESERVED", "PENDING_CONFIRMATION")),
                )
                .distinct()
            )
        ).all()
    )
    enqueued = 0
    settings = get_settings()
    for order, buyer in expiring_orders:
        await enqueue_notification(
            db,
            user_id=buyer.user_id,
            recipient=buyer.user_id,
            event_type="RESERVATION_EXPIRING_SOON",
            idempotency_key=f"reservation-expiring:{order.id}",
            text=(
                f"Резерв заказа {order.order_number} скоро истечёт — "
                "поставщики должны подтвердить наличие."
            ),
            bot_scope="BUYER",
            deep_link=(
                f"{settings.public_base_url.rstrip('/')}"
                f"{settings.buyer_app_path}/orders/{order.id}"
            ),
        )
        enqueued += 1

    subscription_horizon = now + timedelta(days=3)
    ending_subscriptions = list(
        (
            await db.execute(
                select(Subscription, BuyerProfile)
                .join(BuyerProfile, BuyerProfile.id == Subscription.buyer_profile_id)
                .where(
                    Subscription.status.in_(("TRIAL", "ACTIVE")),
                    Subscription.ends_at > now,
                    Subscription.ends_at <= subscription_horizon,
                )
            )
        ).all()
    )
    for subscription, buyer in ending_subscriptions:
        await enqueue_notification(
            db,
            user_id=buyer.user_id,
            recipient=buyer.user_id,
            event_type="SUBSCRIPTION_EXPIRING_SOON",
            idempotency_key=f"subscription-expiring:{subscription.id}",
            text=(
                "Подписка скоро закончится: "
                f"{subscription.ends_at:%d.%m.%Y %H:%M}. Продлите доступ заранее."
            ),
            bot_scope="BUYER",
            deep_link=(
                f"{settings.public_base_url.rstrip('/')}"
                f"{settings.buyer_app_path}/subscription"
            ),
        )
        enqueued += 1
    return enqueued


async def deliver_claimed(db: AsyncSession, notifications: list[Notification]) -> None:
    for notification in notifications:
        scope = str(notification.payload.get("botScope") or "UNKNOWN").upper()
        try:
            if notification.channel != "TELEGRAM":
                raise RuntimeError(f"Unsupported notification channel: {notification.channel}")
            await _send_telegram(notification)
        except Exception as exc:
            # Persist only a bounded, token-free diagnostic string.
            notification.final_error = str(exc)[:1000]
            if notification.attempt_count >= notification.max_attempts:
                notification.status = "FAILED"
                notification.next_attempt_at = None
                result = "failed"
            else:
                notification.status = "RETRY"
                delay = min(300, 2 ** min(notification.attempt_count, 8))
                notification.next_attempt_at = utcnow() + timedelta(seconds=delay)
                result = "retry"
            NOTIFICATION_DELIVERIES.labels(notification.channel, scope, result).inc()
        else:
            notification.status = "SENT"
            notification.sent_at = utcnow()
            notification.next_attempt_at = None
            notification.final_error = None
            NOTIFICATION_DELIVERIES.labels(notification.channel, scope, "sent").inc()
    await db.flush()


async def wait_or_stop(stop: asyncio.Event, seconds: int) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=max(1, seconds))
    except asyncio.TimeoutError:
        return
