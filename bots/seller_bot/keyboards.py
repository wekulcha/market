from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from b2b_common.ui import link_keyboard
from config import settings


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Поделитесь своим контактом",
    )


def seller_links_keyboard():
    rows: list[tuple[str, str] | tuple[str, str, bool]] = [
        ("📋 Мои предложения", settings.app_url("/offers")),
        ("➕ Новое предложение", settings.app_url("/offers/new")),
        ("📦 Заказы", settings.app_url("/orders")),
    ]
    if settings.support_url:
        rows.append(("💬 Поддержка", settings.support_url, False))
    return link_keyboard(*rows)
