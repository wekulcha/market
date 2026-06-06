from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from config import ADMIN_MINI_APP_URL, SUPPORT_LINK


def _orders_button() -> KeyboardButton:
    if ADMIN_MINI_APP_URL.startswith("https://"):
        return KeyboardButton(text="📥 Активные заказы", web_app=WebAppInfo(url=ADMIN_MINI_APP_URL))
    return KeyboardButton(text="📥 Активные заказы")


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [_orders_button()],
            [KeyboardButton(text="📊 Итоги за сегодня")],
            [KeyboardButton(text="💬 Поддержка", url=SUPPORT_LINK)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )
