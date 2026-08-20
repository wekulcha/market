from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove
from b2b_common.api import BotAPIError, InternalBotAPI
from b2b_common.ui import display_status, link_keyboard, safe_text
from config import settings
from keyboards import buyer_links_keyboard, contact_keyboard

logger = logging.getLogger(__name__)
router = Router(name="b2b-buyer")
_INVITE_RE = re.compile(r"^[A-Za-z0-9_-]{20,192}$")


class BuyerRegistration(StatesGroup):
    waiting_for_contact = State()


def _invite_from_start(command: CommandObject) -> str | None:
    raw = (command.args or "").strip()
    if not raw.startswith("invite_"):
        return None
    token = raw.removeprefix("invite_")
    return token if _INVITE_RE.fullmatch(token) else None


def _has_buyer_profile(payload: dict) -> bool:
    role = str(payload.get("role") or "").upper()
    roles = {str(item).upper() for item in (payload.get("roles") or [])}
    return bool(
        role == "BUYER"
        or "BUYER" in roles
        or payload.get("buyer")
        or payload.get("buyerProfileId")
    )


async def _status_or_none(api_client: InternalBotAPI, telegram_id: int) -> dict | None:
    try:
        return await api_client.status(telegram_id)
    except BotAPIError as exc:
        if exc.status_code != 404:
            logger.warning("Buyer status request failed with HTTP %s", exc.status_code)
        return None


@router.message(CommandStart())
async def start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    api_client: InternalBotAPI,
) -> None:
    user = message.from_user
    if user is None:
        return

    invite_token = _invite_from_start(command)
    current = await _status_or_none(api_client, user.id)
    if current and _has_buyer_profile(current):
        await state.clear()
        await message.answer(
            f"<b>{safe_text(settings.app_name)}</b>\nРады снова вас видеть.",
            reply_markup=buyer_links_keyboard(),
        )
        return

    if not invite_token:
        await state.clear()
        await message.answer(
            f"<b>{safe_text(settings.app_name)}</b>\n"
            "Регистрация покупателей доступна только по персональной ссылке. "
            "Попросите приглашение у администратора.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await state.set_state(BuyerRegistration.waiting_for_contact)
    await state.update_data(invite_token=invite_token)
    await message.answer(
        f"<b>Добро пожаловать в {safe_text(settings.app_name)}!</b>\n"
        "Чтобы активировать приглашение, отправьте свой номер кнопкой ниже.",
        reply_markup=contact_keyboard(),
    )


@router.message(BuyerRegistration.waiting_for_contact, F.contact)
async def register_contact(
    message: Message,
    state: FSMContext,
    api_client: InternalBotAPI,
) -> None:
    user = message.from_user
    contact = message.contact
    if user is None or contact is None:
        return
    if contact.user_id is None or int(contact.user_id) != int(user.id):
        await message.answer(
            "Нужно отправить именно свой контакт через кнопку «Отправить мой номер».",
            reply_markup=contact_keyboard(),
        )
        return

    data = await state.get_data()
    invite_token = str(data.get("invite_token") or "")
    if not _INVITE_RE.fullmatch(invite_token):
        await state.clear()
        await message.answer(
            "Приглашение потеряло силу. Откройте персональную ссылку ещё раз."
        )
        return

    try:
        await api_client.register_buyer(
            telegram_id=user.id,
            username=user.username,
            phone=contact.phone_number,
            invite_token=invite_token,
        )
    except BotAPIError as exc:
        logger.warning("Buyer registration failed with HTTP %s", exc.status_code)
        await message.answer(
            safe_text(exc.public_message),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await state.clear()
    await message.answer(
        "<b>Регистрация завершена.</b> Заполните данные компании и адрес доставки в приложении.",
        reply_markup=buyer_links_keyboard(),
    )


@router.message(Command("catalog"))
async def catalog(message: Message) -> None:
    await message.answer(
        "Каталог оптовых предложений:",
        reply_markup=link_keyboard(("🛍 Открыть каталог", settings.app_url("/catalog"))),
    )


@router.message(Command("orders"))
async def orders(message: Message) -> None:
    await message.answer(
        "Ваши заказы:",
        reply_markup=link_keyboard(("📦 Открыть заказы", settings.app_url("/orders"))),
    )


@router.message(Command("subscription"))
async def subscription(message: Message, api_client: InternalBotAPI) -> None:
    user = message.from_user
    if user is None:
        return
    try:
        payload = await api_client.status(user.id)
    except BotAPIError as exc:
        logger.warning(
            "Buyer subscription request failed with HTTP %s", exc.status_code
        )
        await message.answer(safe_text(exc.public_message))
        return
    expires_at = payload.get("subscriptionExpiresAt") or payload.get("expiresAt")
    expires_line = (
        f"\nДействует до: <b>{safe_text(expires_at)}</b>" if expires_at else ""
    )
    await message.answer(
        f"Статус подписки: <b>{display_status(payload)}</b>{expires_line}",
        reply_markup=link_keyboard(
            ("💳 Управление подпиской", settings.app_url("/subscription"))
        ),
    )


@router.message(Command("support"))
async def support(message: Message) -> None:
    if settings.support_url:
        await message.answer(
            "Связаться с поддержкой:",
            reply_markup=link_keyboard(("💬 Поддержка", settings.support_url, False)),
        )
        return
    await message.answer(
        "Контакт поддержки пока не настроен. Сообщите администратору платформы."
    )
