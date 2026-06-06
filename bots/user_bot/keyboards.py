from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from config import SUPPORT_LINK, USER_MINI_APP_BASE, USER_MINI_APP_VERSION


def _with_version(url: str) -> str:
    if USER_MINI_APP_VERSION:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}v={USER_MINI_APP_VERSION}"
    return url


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    base = USER_MINI_APP_BASE.rstrip("/")
    if base.startswith("https://"):
        catalog_url = _with_version(f"{base}/catalog")
        cart_url = _with_version(f"{base}/cart")
        profile_url = _with_version(f"{base}/profile")
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🛒 Каталог", web_app=WebAppInfo(url=catalog_url))],
                [
                    KeyboardButton(text="🧺 Корзина", web_app=WebAppInfo(url=cart_url)),
                    KeyboardButton(text="👤 Профиль", web_app=WebAppInfo(url=profile_url)),
                ],
                [KeyboardButton(text="📦 Статус заказа")],
                [KeyboardButton(text="💬 Поддержка", url=SUPPORT_LINK)],
            ],
            resize_keyboard=True,
            input_field_placeholder="Выберите действие",
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Каталог")],
            [KeyboardButton(text="🧺 Корзина"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="📦 Статус заказа")],
            [KeyboardButton(text="💬 Поддержка", url=SUPPORT_LINK)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def request_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер", request_contact=True)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Поделитесь номером телефона",
    )
