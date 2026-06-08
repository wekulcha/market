from __future__ import annotations

import html
import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import async_session
from app.models.order import Order
from app.models.order_position import OrderPosition
from app.models.staff import Staff
from app.services import telegram_bot_client
from app.services.restaurant_hours import delivery_day_label, restaurant_delivery_cutoff

logger = logging.getLogger(__name__)


_STATUS_RU: dict[str, str] = {
    "CREATED": "Принят",
    "ACCEPTED": "Собран",
    "COOKING": "Собран",
    "DELIVERY": "Собран",
    "DONE": "Завершён",
    "CANCELLED": "Отменён",
}

_ORDER_TYPE_RU: dict[str, str] = {
    "DELIVERY": "Доставка",
    "DINE_IN": "На месте",
}


def _esc(s: str | None) -> str:
    return html.escape(s or "")


def _enum_key(v: object) -> str:
    if hasattr(v, "value"):
        return str(getattr(v, "value"))
    return str(v)


def _status_ru(status: object) -> str:
    return _STATUS_RU.get(_enum_key(status), _enum_key(status))


def _order_type_ru(ot: object) -> str:
    return _ORDER_TYPE_RU.get(_enum_key(ot), _enum_key(ot))


def _compact_place_text(v: str | None) -> str:
    if not v:
        return "—"
    t = " ".join(v.split())
    t = t.replace("·", "-")
    t = t.replace(" - ", "-").replace(" -", "-").replace("- ", "-")
    return t


def _username_at(username: str | None) -> str:
    if not username:
        return "—"
    u = username.strip()
    if u.startswith("@"):
        return u
    return f"@{u}"


def _phone_clickable(phone: str | None) -> str:
    """Текст для HTML: ссылка tel: с +"""
    if not phone:
        return "—"
    p = phone.strip()
    if p.startswith("tg-"):
        return _esc(p)
    digits = "".join(c for c in p if c.isdigit() or c == "+")
    if not digits:
        return _esc(p)
    if digits.startswith("+"):
        tel = digits
        show = digits
    else:
        tel = f"+{digits}"
        show = tel
    return f'<a href="tel:{_esc(tel)}">{_esc(show)}</a>'


def _user_tg_link(username: str | None, telegram_id: int) -> str:
    """Возвращает упоминание без web-preview карточки."""
    if username:
        u = username.strip().lstrip("@")
        if u:
            return f"@{_esc(u)}"
    return f"id:{telegram_id}"


def _format_user_order_block(
    order: Order,
    lines: list[OrderPosition],
    title: str,
    *,
    is_update: bool = False,
) -> str:
    delivery_day = delivery_day_label(order.restaurant)
    cutoff = restaurant_delivery_cutoff(order.restaurant)
    parts = [
        f"🍽 <b>{_esc(title)}</b>",
        "━━━━━━━━━━━━━━",
        f"№ <code>{order.id}</code>",
        f"📍 {_esc(order.restaurant.name)}",
        f"📌 Статус: <b>{_status_ru(order.status)}</b>",
        f"🧾 {_order_type_ru(order.order_type)}",
        f"🚚 Доставим: <b>{delivery_day}</b> (заказы до {cutoff} — сегодня)",
        f"💰 Сумма: <b>{order.total} ₽</b>",
        "",
        "<b>Состав:</b>",
    ]
    for p in lines:
        parts.append(f"• {_esc(p.meal.name)} × {p.quantity} — {p.total_price} ₽")
    if order.delivery_address:
        parts.append(f"\n🚚 Адрес: {_esc(order.delivery_address)}")
    if order.table_number:
        parts.append(f"\n🪑 Место: <b>{_esc(order.table_number)}</b>")
    if is_update:
        parts.append("\n<i>Статус обновлён. При следующем изменении пришлём новое сообщение.</i>")
    else:
        parts.append("\n<i>Мы пришлём обновление, когда статус изменится.</i>")
    return "\n".join(parts)


def _format_admin_new_order(order: Order, lines: list[OrderPosition]) -> str:
    user = order.user
    uname = _user_tg_link(user.username, user.id)
    phone = _phone_clickable(user.phone)
    status_ru = _status_ru(order.status)
    paid = "✅ Оплачен" if getattr(order, "is_paid", False) else "❌ Не оплачен"
    delivery_day = delivery_day_label(order.restaurant)
    cutoff = restaurant_delivery_cutoff(order.restaurant)
    if _enum_key(order.order_type) == "DINE_IN":
        place = f"🪑 Место: <b>{_esc(_compact_place_text(order.table_number))}</b>"
    else:
        place = f"🚚 Адрес: <b>{_esc(_compact_place_text(order.delivery_address))}</b>"
    parts = [
        "🔔 <b>Новый заказ</b>",
        "━━━━━━━━━━━━━━",
        f"№ <code>{order.id}</code> · <b>{status_ru}</b>",
        f"👤 {uname} · {phone}",
        f"{place}",
        f"🚚 Доставим: <b>{delivery_day}</b> · дедлайн {cutoff}",
        f"💰 <b>{order.total} ₽</b> · {paid}",
        "",
        "<b>Позиции:</b>",
    ]
    for p in lines:
        parts.append(f"• {_esc(p.meal.name)} × {p.quantity}")
    if order.comment:
        parts.append(f"\n💬 Комментарий: {_esc(order.comment)}")
    parts.append("\n<i>Статус ещё не меняли</i>")
    return "\n".join(parts)


def _build_admin_keyboard(order_id: int) -> dict:
    """Новый заказ: отмена слева, сборка справа. Дальше клавиатура обновляется из бота."""
    return {
        "inline_keyboard": [
            [
                {"text": "❌ Отмена", "callback_data": f"k:{order_id}:CAN"},
                {"text": "🧺 Собран", "callback_data": f"k:{order_id}:ACC"},
            ]
        ]
    }


async def notify_order_placed(db: AsyncSession, order_id: int) -> None:
    settings = get_settings()

    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant))
        .where(Order.id == order_id)
    )
    order = result.unique().scalar_one_or_none()
    if not order:
        return

    lines_result = await db.execute(
        select(OrderPosition)
        .options(joinedload(OrderPosition.meal))
        .where(OrderPosition.order_id == order_id)
    )
    lines = list(lines_result.unique().scalars().all())

    user_token = settings.user_bot_token
    if user_token:
        msg = _format_user_order_block(order, lines, "Заказ оформлен", is_update=False)
        mid = await telegram_bot_client.send_message(user_token, order.user.id, msg)
        if mid is not None:
            order.user_telegram_notify_message_id = mid
            await db.flush()

    admin_token = settings.admin_bot_token
    if admin_token:
        admin_html = _format_admin_new_order(order, lines)
        keyboard = _build_admin_keyboard(order.id)

        group_chat_id = getattr(order.restaurant, "telegram_group_chat_id", None)
        if group_chat_id is not None:
            sent_mid = await telegram_bot_client.send_message(
                admin_token, int(group_chat_id), admin_html, reply_markup=keyboard
            )
            if sent_mid is not None:
                return
            logger.warning(
                "Failed to send order %s to restaurant group chat_id=%s; fallback to staff DMs",
                order.id,
                group_chat_id,
            )

        staff_result = await db.execute(
            select(Staff)
            .options(joinedload(Staff.user))
            .where(Staff.restaurant_id == order.restaurant_id)
        )
        staff_list = staff_result.unique().scalars().all()
        seen_user_ids: set[int] = set()
        for s in staff_list:
            uid = int(s.user_id)
            if uid in seen_user_ids:
                continue
            seen_user_ids.add(uid)
            await telegram_bot_client.send_message(
                admin_token, s.user.id, admin_html, reply_markup=keyboard
            )


async def notify_order_placed_detached(order_id: int) -> None:
    async with async_session() as db:
        try:
            await notify_order_placed(db, order_id)
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Failed to send order placed notifications for order_id=%s", order_id)


async def notify_user_status_changed(db: AsyncSession, order_id: int) -> None:
    settings = get_settings()
    user_token = settings.user_bot_token
    if not user_token:
        return

    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant))
        .where(Order.id == order_id)
    )
    order = result.unique().scalar_one_or_none()
    if not order:
        return

    lines_result = await db.execute(
        select(OrderPosition)
        .options(joinedload(OrderPosition.meal))
        .where(OrderPosition.order_id == order_id)
    )
    lines = list(lines_result.unique().scalars().all())

    chat_id = order.user.id
    old_mid = order.user_telegram_notify_message_id
    if old_mid:
        await telegram_bot_client.delete_message(user_token, chat_id, old_mid)

    msg = _format_user_order_block(order, lines, "Обновление заказа", is_update=True)
    mid = await telegram_bot_client.send_message(user_token, chat_id, msg)
    if mid is not None:
        order.user_telegram_notify_message_id = mid
        await db.flush()
