from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardRemove
from b2b_common.api import BotAPIError, InternalBotAPI
from b2b_common.ui import link_keyboard, safe_text
from config import settings
from keyboards import contact_keyboard, seller_links_keyboard

logger = logging.getLogger(__name__)
router = Router(name="b2b-seller")


def _has_seller_profile(payload: dict) -> bool:
    role = str(payload.get("role") or "").upper()
    roles = {str(item).upper() for item in (payload.get("roles") or [])}
    return bool(
        role == "SELLER"
        or "SELLER" in roles
        or payload.get("seller")
        or payload.get("sellerProfileId")
    )


@router.message(CommandStart())
async def start(message: Message, api_client: InternalBotAPI) -> None:
    user = message.from_user
    if user is None:
        return
    try:
        current = await api_client.status(user.id)
    except BotAPIError as exc:
        current = None
        if exc.status_code != 404:
            logger.warning("Seller status request failed with HTTP %s", exc.status_code)

    if current and _has_seller_profile(current):
        await message.answer(
            f"<b>{safe_text(settings.app_name)} для поставщиков</b>\nРады снова вас видеть.",
            reply_markup=seller_links_keyboard(),
        )
        return

    await message.answer(
        f"<b>{safe_text(settings.app_name)} для поставщиков</b>\n"
        "Отправьте свой номер кнопкой ниже. После регистрации заполните профиль компании в приложении.",
        reply_markup=contact_keyboard(),
    )


@router.message(F.contact)
async def register_contact(message: Message, api_client: InternalBotAPI) -> None:
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

    try:
        await api_client.register_seller(
            telegram_id=user.id,
            username=user.username,
            phone=contact.phone_number,
        )
    except BotAPIError as exc:
        logger.warning("Seller registration failed with HTTP %s", exc.status_code)
        await message.answer(
            safe_text(exc.public_message),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await message.answer(
        "<b>Регистрация начата.</b> Заполните реквизиты и точку забора в приложении.",
        reply_markup=seller_links_keyboard(),
    )


@router.message(Command("offers"))
async def offers(message: Message) -> None:
    await message.answer(
        "Ваши предложения:",
        reply_markup=link_keyboard(
            ("📋 Открыть предложения", settings.app_url("/offers"))
        ),
    )


@router.message(Command("new_offer"))
async def new_offer(message: Message) -> None:
    await message.answer(
        "Создать черновик предложения:",
        reply_markup=link_keyboard(
            ("➕ Новое предложение", settings.app_url("/offers/new"))
        ),
    )


@router.message(Command("orders"))
async def orders(message: Message) -> None:
    await message.answer(
        "Заказы и резервы, требующие подготовки:",
        reply_markup=link_keyboard(("📦 Открыть заказы", settings.app_url("/orders"))),
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
