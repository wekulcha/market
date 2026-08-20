from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from b2b_common.ui import app_button, link_keyboard
from config import settings


def admin_links_keyboard():
    rows: list[tuple[str, str] | tuple[str, str, bool]] = [
        ("📊 Открыть админку", settings.app_url()),
        ("🧾 Модерация предложений", settings.app_url("/offers?status=moderation")),
        ("📦 Заказы", settings.app_url("/orders")),
    ]
    if settings.support_url:
        rows.append(("💬 Поддержка", settings.support_url, False))
    return link_keyboard(*rows)


def offer_quick_actions_keyboard(offer_id: str) -> InlineKeyboardMarkup:
    """Callback contract used by admin notifications from the notification worker."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=f"b2b:approve:{offer_id}",
                ),
                InlineKeyboardButton(
                    text="↩️ На доработку",
                    callback_data=f"b2b:request_changes:{offer_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"b2b:reject:{offer_id}",
                ),
                app_button("🔎 Открыть", settings.app_url(f"/offers/{offer_id}")),
            ],
        ]
    )


def confirmation_keyboard(offer_id: str, action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=f"b2b_confirm:{offer_id}:{action}",
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=f"b2b_cancel:{offer_id}",
                ),
            ]
        ]
    )
