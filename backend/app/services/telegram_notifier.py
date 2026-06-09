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


def _format_admin_delivery_address(address: str | None) -> str:
    if not address:
        return "—"
    raw = " ".join(address.split())
    parts = [part.strip() for part in raw.split("·")]
    if len(parts) >= 5:
        street, house, entrance, floor, apartment = parts[:5]
        map_parts = [
            street,
            f"д. {house}" if house else "",
            f"п. {entrance}" if entrance else "",
        ]
        map_text = ", ".join(part for part in map_parts if part)
        details: list[str] = []
        if floor and apartment:
            details.append(f"кв. {floor}-{apartment}")
        elif apartment:
            details.append(f"кв. {apartment}")
        elif floor:
            details.append(f"эт. {floor}")
        suffix = f", {_esc(', '.join(details))}" if details else ""
        return f"<code>{_esc(map_text)}</code>{suffix}"
    return _esc(raw)


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
    if _enum_key(order.status) == "DONE":
        if order.review_rating:
            parts.append(f"\n⭐ Спасибо за оценку: <b>{order.review_rating}⭐</b>")
        else:
            parts.append(
                "\n⭐ <b>Оцените заказ</b>\n"
                "Нажмите на оценку ниже. После оценки можно написать отзыв одним сообщением."
            )
    elif is_update:
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
    if _enum_key(order.order_type) == "DINE_IN":
        place = f"🪑 Место: <b>{_esc(_compact_place_text(order.table_number))}</b>"
    else:
        place = f"🚚 Адрес: {_format_admin_delivery_address(order.delivery_address)}"
    parts = [
        "🔔 <b>Новый заказ</b>",
        "━━━━━━━━━━━━━━",
        f"№ <code>{order.id}</code> · <b>{status_ru}</b>",
        f"👤 {uname} · {phone}",
        f"{place}",
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


def _build_review_keyboard(order_id: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": f"{rating}⭐", "callback_data": f"r:{order_id}:{rating}"}
                for rating in range(1, 6)
            ]
        ]
    }


def _format_admin_order_review(order: Order) -> str:
    user = order.user
    uname = _user_tg_link(user.username, user.id)
    phone = _phone_clickable(user.phone)
    rating = order.review_rating or "—"
    parts = [
        "⭐ <b>Отзыв по заказу</b>",
        "━━━━━━━━━━━━━━",
        f"№ <code>{order.id}</code> · {_esc(order.restaurant.name)}",
        f"👤 {uname} · {phone}",
        f"Оценка: <b>{rating}⭐</b>",
    ]
    if order.review_text:
        parts.append(f"\n💬 {_esc(order.review_text)}")
    else:
        parts.append("\n<i>Пользователь оставил оценку без текста.</i>")
    return "\n".join(parts)


def _review_admin_messages(order: Order) -> list[dict[str, int]]:
    raw_messages = order.review_admin_messages
    if not isinstance(raw_messages, list):
        return []

    messages: list[dict[str, int]] = []
    for raw in raw_messages:
        if not isinstance(raw, dict):
            continue
        try:
            chat_id = int(raw.get("chat_id") or 0)
            message_id = int(raw.get("message_id") or 0)
        except (TypeError, ValueError):
            continue
        if chat_id and message_id > 0:
            messages.append({"chat_id": chat_id, "message_id": message_id})
    return messages


async def _set_review_admin_messages(
    db: AsyncSession, order: Order, messages: list[dict[str, int]]
) -> None:
    order.review_admin_messages = messages or None
    await db.flush()


async def _edit_order_review_admin_messages(
    db: AsyncSession, admin_token: str, order: Order, admin_html: str
) -> bool:
    messages = _review_admin_messages(order)
    if not messages:
        return False

    edited_messages: list[dict[str, int]] = []
    for item in messages:
        ok = await telegram_bot_client.edit_message_text(
            admin_token,
            item["chat_id"],
            item["message_id"],
            admin_html,
        )
        if ok:
            edited_messages.append(item)
        else:
            logger.warning(
                "Failed to edit review notification for order %s chat_id=%s message_id=%s",
                order.id,
                item["chat_id"],
                item["message_id"],
            )

    if edited_messages != messages:
        await _set_review_admin_messages(db, order, edited_messages)

    return bool(edited_messages)


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
    keyboard = None
    if _enum_key(order.status) == "DONE" and not order.review_rating:
        keyboard = _build_review_keyboard(order.id)
    mid = await telegram_bot_client.send_message(user_token, chat_id, msg, reply_markup=keyboard)
    if mid is not None:
        order.user_telegram_notify_message_id = mid
        await db.flush()


async def notify_order_review(db: AsyncSession, order_id: int) -> None:
    settings = get_settings()
    admin_token = settings.admin_bot_token
    if not admin_token:
        return

    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant))
        .where(Order.id == order_id)
    )
    order = result.unique().scalar_one_or_none()
    if not order or not order.review_rating:
        return

    admin_html = _format_admin_order_review(order)
    if await _edit_order_review_admin_messages(db, admin_token, order, admin_html):
        return

    sent_messages: list[dict[str, int]] = []
    group_chat_id = getattr(order.restaurant, "telegram_group_chat_id", None)
    if group_chat_id is not None:
        chat_id = int(group_chat_id)
        sent_mid = await telegram_bot_client.send_message(admin_token, chat_id, admin_html)
        if sent_mid is not None:
            await _set_review_admin_messages(
                db,
                order,
                [{"chat_id": chat_id, "message_id": int(sent_mid)}],
            )
            return
        logger.warning(
            "Failed to send review for order %s to restaurant group chat_id=%s; fallback to staff DMs",
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
    for staff in staff_list:
        uid = int(staff.user_id)
        if uid in seen_user_ids:
            continue
        seen_user_ids.add(uid)
        chat_id = int(staff.user.id)
        sent_mid = await telegram_bot_client.send_message(admin_token, chat_id, admin_html)
        if sent_mid is not None:
            sent_messages.append({"chat_id": chat_id, "message_id": int(sent_mid)})

    if sent_messages:
        await _set_review_admin_messages(db, order, sent_messages)


async def notify_order_review_detached(order_id: int) -> None:
    async with async_session() as db:
        try:
            await notify_order_review(db, order_id)
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Failed to send order review notifications for order_id=%s", order_id)
