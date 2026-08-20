from __future__ import annotations

import logging
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from b2b_common.api import BotAPIError, InternalBotAPI
from b2b_common.ui import link_keyboard, safe_text
from config import settings
from keyboards import (
    admin_links_keyboard,
    confirmation_keyboard,
    offer_quick_actions_keyboard,
)

logger = logging.getLogger(__name__)
router = Router(name="b2b-admin")
_ALLOWED_ACTIONS = {"approve", "reject", "request_changes"}
_ACTION_LABELS = {
    "approve": "одобрить предложение",
    "reject": "отклонить предложение",
    "request_changes": "вернуть предложение на доработку",
}
_DEFAULT_REASONS = {
    "reject": "Отклонено администратором через Telegram",
    "request_changes": "Требуются исправления; подробности доступны в админке",
}


def _allowed(user_id: int | None) -> bool:
    return user_id is not None and user_id in settings.admin_telegram_ids


async def _require_message_access(message: Message) -> bool:
    user_id = message.from_user.id if message.from_user else None
    if _allowed(user_id):
        return True
    await message.answer("Нет доступа.")
    return False


async def _require_callback_access(query: CallbackQuery) -> bool:
    if _allowed(query.from_user.id):
        return True
    await query.answer("Нет доступа.", show_alert=True)
    return False


def _parse_offer_id(value: str) -> str | None:
    try:
        return str(UUID(value))
    except ValueError:
        return None


def _parse_callback(data: str | None, prefix: str) -> tuple[str, str] | None:
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != prefix:
        return None
    offer_id = _parse_offer_id(parts[1])
    action = parts[2]
    if offer_id is None or action not in _ALLOWED_ACTIONS:
        return None
    return offer_id, action


def _parse_offer_action(data: str | None) -> tuple[str, str] | None:
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != "b2b":
        return None
    action = parts[1]
    offer_id = _parse_offer_id(parts[2])
    if offer_id is None or action not in _ALLOWED_ACTIONS:
        return None
    return offer_id, action


@router.message(CommandStart())
async def start(message: Message) -> None:
    if not await _require_message_access(message):
        return
    await message.answer(
        f"<b>{safe_text(settings.app_name)} · оперативная админка</b>\n"
        "Здесь приходят уведомления и безопасные быстрые действия. "
        "Полное управление доступно в веб-админке.",
        reply_markup=admin_links_keyboard(),
    )


@router.message(Command("offers"))
async def offers(message: Message) -> None:
    if not await _require_message_access(message):
        return
    await message.answer(
        "Предложения на модерации:",
        reply_markup=link_keyboard(
            ("🧾 Открыть модерацию", settings.app_url("/offers?status=moderation"))
        ),
    )


@router.message(Command("orders"))
async def orders(message: Message) -> None:
    if not await _require_message_access(message):
        return
    await message.answer(
        "Заказы, требующие внимания:",
        reply_markup=link_keyboard(("📦 Открыть заказы", settings.app_url("/orders"))),
    )


@router.message(Command("dashboard"))
async def dashboard(message: Message) -> None:
    if not await _require_message_access(message):
        return
    await message.answer(
        "Операционный dashboard:",
        reply_markup=link_keyboard(("📊 Открыть dashboard", settings.app_url())),
    )


@router.message(Command("support"))
async def support(message: Message) -> None:
    if not await _require_message_access(message):
        return
    if settings.support_url:
        await message.answer(
            "Связаться с поддержкой:",
            reply_markup=link_keyboard(("💬 Поддержка", settings.support_url, False)),
        )
        return
    await message.answer("Контакт поддержки пока не настроен.")


@router.callback_query(F.data.startswith("b2b:"))
async def request_offer_action(query: CallbackQuery) -> None:
    if not await _require_callback_access(query):
        return
    parsed = _parse_offer_action(query.data)
    if not parsed:
        await query.answer("Некорректное действие.", show_alert=True)
        return
    offer_id, action = parsed
    await query.answer()
    if query.message:
        await query.message.answer(
            f"Подтвердите действие: <b>{safe_text(_ACTION_LABELS[action])}</b> "
            f"для предложения №<code>{offer_id}</code>.",
            reply_markup=confirmation_keyboard(offer_id, action),
        )


@router.callback_query(F.data.startswith("b2b_cancel:"))
async def cancel_offer_action(query: CallbackQuery) -> None:
    if not await _require_callback_access(query):
        return
    parts = (query.data or "").split(":")
    if len(parts) != 2:
        await query.answer("Некорректное действие.", show_alert=True)
        return
    offer_id = _parse_offer_id(parts[1])
    if offer_id is None:
        await query.answer("Некорректное действие.", show_alert=True)
        return
    await query.answer("Отменено")
    if query.message:
        await query.message.edit_reply_markup(
            reply_markup=offer_quick_actions_keyboard(offer_id)
        )


@router.callback_query(F.data.startswith("b2b_confirm:"))
async def confirm_offer_action(
    query: CallbackQuery, api_client: InternalBotAPI
) -> None:
    if not await _require_callback_access(query):
        return
    parsed = _parse_callback(query.data, "b2b_confirm")
    if not parsed:
        await query.answer("Некорректное действие.", show_alert=True)
        return
    offer_id, action = parsed
    try:
        result = await api_client.admin_offer_action(
            offer_id=offer_id,
            action=action,
            actor_telegram_id=query.from_user.id,
            reason=_DEFAULT_REASONS.get(action),
        )
    except BotAPIError as exc:
        logger.warning("Admin quick action failed with HTTP %s", exc.status_code)
        await query.answer(safe_text(exc.public_message), show_alert=True)
        return

    await query.answer("Действие выполнено")
    if query.message:
        await query.message.edit_reply_markup(reply_markup=None)
        status = result.get("status") or action
        await query.message.answer(
            f"Предложение №<code>{offer_id}</code>: <b>{safe_text(status)}</b>."
        )
