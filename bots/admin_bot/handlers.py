import hashlib
import html
import hmac as _hmac
import time

import httpx
from aiogram import Router, F
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from aiogram.filters import CommandStart

from config import ADMIN_MINI_APP_URL, API_BASE, BOT_TOKEN, INTERNAL_API_SECRET, SUPPORT_LINK
from keyboards import main_menu_keyboard
from order_keyboard import order_status_keyboard
from reporting import build_today_report_messages, build_today_report_pdf


def _generate_bot_auth_token(telegram_id: int, ttl: int = 600) -> str:
    """Генерирует stateless HMAC-токен для верификации через POST /auth/verify-admin-bot-token."""
    expiry = int(time.time()) + ttl
    data = f"{telegram_id}_{expiry}"
    sig = _hmac.new(BOT_TOKEN.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{telegram_id}_{expiry}_{sig}"

router = Router()

STATUS_FROM_CB = {
    "ACC": "ACCEPTED",
    "COO": "COOKING",
    "DEL": "DELIVERY",
    "DON": "DONE",
    "CAN": "CANCELLED",
    "PAY": "PAID",
}

STATUS_RU = {
    "CREATED": "Создан",
    "ACCEPTED": "Принят",
    "COOKING": "Готовится",
    "DELIVERY": "В доставке",
    "DONE": "Выполнен",
    "CANCELLED": "Отменён",
}


def _apply_status_change_meta(
    source_html: str,
    *,
    order_id: int,
    status_ru: str,
    paid_ru: str,
    actor: str,
) -> str:
    lines = source_html.split("\n")
    order_line = f"№ <code>{order_id}</code> · <b>{status_ru}</b>"
    user_line = ""
    place_line = ""
    money_line = f"💰 · {paid_ru}"
    positions_block: list[str] = []
    comment_line = ""
    in_positions = False
    for ln in lines:
        if "Новый заказ" in ln:
            continue
        if ln.startswith(f"№ <code>{order_id}</code>"):
            continue
        if ln.startswith("👤 "):
            user_line = ln
            continue
        if ln.startswith("🚚 ") or ln.startswith("🪑 ") or ln.startswith("Адрес:") or ln.startswith("Место:"):
            place_line = ln
            continue
        if ln.startswith("💰 "):
            left = ln.split("·")[0].strip()
            money_line = f"{left} · {paid_ru}"
            continue
        if ln.startswith("<b>Позиции:</b>"):
            in_positions = True
            positions_block = [ln]
            continue
        if in_positions:
            if ln.strip() == "":
                continue
            if ln.startswith("• "):
                positions_block.append(ln)
                continue
            in_positions = False
        if ln.startswith("💬 "):
            comment_line = ln
            continue
        if "Статус ещё не меняли" in ln or "Статус изменил:" in ln or "Выберите статус ниже" in ln:
            continue

    out: list[str] = [order_line, "━━━━━━━━━━━━━━"]
    if user_line:
        out.append(user_line)
    out.append("")
    if place_line:
        out.append(place_line)
    out.append(money_line)
    out.append("")
    if positions_block:
        out.extend(positions_block)
    if comment_line:
        out.append("")
        out.append(comment_line)
    out.append("")
    out.append(f"<i>Статус изменил: {html.escape(actor)}</i>")
    return "\n".join(out)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "<b>Панель Kulcha Market</b>\n"
        "━━━━━━━━━━━━━━\n"
        "Здесь приходят <b>новые заказы</b> и кнопки смены статуса. "
        "Управление товарами и аналитика — в мини-приложении.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "📥 Активные заказы")
async def active_orders(message: Message):
    if ADMIN_MINI_APP_URL.startswith("https://"):
        uid = message.from_user.id
        token = _generate_bot_auth_token(uid) if BOT_TOKEN else None
        url = f"{ADMIN_MINI_APP_URL}?tg_auth={token}" if token else ADMIN_MINI_APP_URL
        await message.answer(
            "<b>Активные заказы</b>\n"
            "━━━━━━━━━━━━━━\n"
            "Откройте вкладку «Заказы» в панели:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📋 Открыть заказы",
                            web_app=WebAppInfo(url=url),
                        )
                    ]
                ]
            ),
        )
    else:
        await message.answer(
            "<b>Активные заказы</b>\n━━━━━━━━━━━━━━\n"
            f"Откройте в браузере:\n<code>{ADMIN_MINI_APP_URL}</code>"
        )


@router.message(F.text == "💬 Поддержка")
async def support(message: Message):
    await message.answer(f"<b>Поддержка</b>\n━━━━━━━━━━━━━━\n{SUPPORT_LINK}")


@router.message(F.text == "📊 Итоги за сегодня")
async def today_summary(message: Message):
    if not BOT_TOKEN:
        await message.answer("Не задан токен админ-бота. Отчёт недоступен.")
        return

    token = _generate_bot_auth_token(message.from_user.id)
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(
                f"{API_BASE}/orders/today-summary",
                headers={"X-Kulcha-Bot-Auth": token},
            )
    except Exception as exc:
        await message.answer(f"Не удалось получить отчёт: {html.escape(str(exc))}")
        return

    if response.status_code != 200:
        detail = ""
        try:
            payload = response.json()
            detail = str(payload.get("detail") or "")
        except Exception:
            detail = response.text[:300]
        suffix = f"\n{html.escape(detail)}" if detail else ""
        await message.answer(
            "<b>Итоги за сегодня</b>\n"
            "━━━━━━━━━━━━━━\n"
            f"Ошибка API: {response.status_code}{suffix}"
        )
        return

    summary = response.json()
    for chunk in build_today_report_messages(summary):
        await message.answer(chunk)

    pdf_bytes = build_today_report_pdf(summary)
    if pdf_bytes:
        report_date = str(summary.get("reportDate") or "today")
        filename = f"kulcha-today-summary-{report_date}.pdf"
        await message.answer_document(
            BufferedInputFile(pdf_bytes, filename=filename),
            caption="PDF-версия отчёта за сегодня",
        )


@router.callback_query(F.data.startswith("k:"))
async def order_status_callback(query: CallbackQuery):
    if not INTERNAL_API_SECRET:
        await query.answer("Не задан KULCHA_INTERNAL_API_SECRET", show_alert=True)
        return
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer()
        return
    try:
        order_id = int(parts[1])
    except ValueError:
        await query.answer()
        return
    code = parts[2]
    status = STATUS_FROM_CB.get(code)
    if not status:
        await query.answer("Неизвестный код", show_alert=True)
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if status == "PAID":
                r = await client.patch(
                    f"{API_BASE}/orders/{order_id}/paid",
                    headers={
                        "X-Kulcha-Internal-Secret": INTERNAL_API_SECRET,
                        "Content-Type": "application/json",
                    },
                    json={"isPaid": True},
                )
            else:
                r = await client.patch(
                    f"{API_BASE}/orders/{order_id}/status",
                    headers={
                        "X-Kulcha-Internal-Secret": INTERNAL_API_SECRET,
                        "Content-Type": "application/json",
                    },
                    json={"status": status},
                )
        if r.status_code == 200:
            await query.answer("Оплата отмечена ✓" if status == "PAID" else "Статус обновлён ✓")
            if query.message:
                try:
                    data = r.json() if r.content else {}
                    st = str(data.get("status") or "")
                    is_paid = bool(data.get("isPaid"))
                    new_kb = order_status_keyboard(order_id, st, is_paid)
                    who = query.from_user
                    who_name = f"@{who.username}" if who and who.username else f"id:{who.id if who else '—'}"
                    base_text = query.message.html_text or query.message.text or ""
                    if base_text:
                        new_text = _apply_status_change_meta(
                            base_text,
                            order_id=order_id,
                            status_ru=STATUS_RU.get(st, st),
                            paid_ru="✅ Оплачен" if is_paid else "❌ Не оплачен",
                            actor=who_name,
                        )
                        await query.message.edit_text(new_text, reply_markup=new_kb)
                    else:
                        await query.message.edit_reply_markup(reply_markup=new_kb)
                except Exception:
                    pass
        else:
            await query.answer(f"Ошибка API: {r.status_code}", show_alert=True)
    except Exception as e:
        await query.answer(f"Ошибка: {e}", show_alert=True)
