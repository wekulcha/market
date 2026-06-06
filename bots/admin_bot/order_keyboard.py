"""Клавиатура статусов заказа в Telegram (синхронно с логикой после PATCH)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def order_status_keyboard(order_id: int, status: str, is_paid: bool = False) -> InlineKeyboardMarkup | None:
    if status == "DONE":
        row = []
        if not is_paid:
            row.append(InlineKeyboardButton(text="💸 Оплачен", callback_data=f"k:{order_id}:PAY"))
        return InlineKeyboardMarkup(inline_keyboard=[row]) if row else None
    if status == "CANCELLED":
        return None
    if status == "CREATED":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="❌ Отмена", callback_data=f"k:{order_id}:CAN"),
                    InlineKeyboardButton(text="✅ Принят", callback_data=f"k:{order_id}:ACC"),
                ]
            ]
        )
    if status == "ACCEPTED":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="👨‍🍳 Готовится", callback_data=f"k:{order_id}:COO"),
                    InlineKeyboardButton(text="🚚 Доставка", callback_data=f"k:{order_id}:DEL"),
                ]
            ]
        )
    if status == "COOKING":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🚚 Доставка", callback_data=f"k:{order_id}:DEL"),
                ]
            ]
        )
    if status == "DELIVERY":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✔️ Готово", callback_data=f"k:{order_id}:DON"),
                ]
            ]
        )
    return None
