import hashlib
import html
import hmac as _hmac
import re
import time
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Any

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

WEIGHT_COMMAND_HELP = (
    "Не смог разобрать вес.\n"
    "Напишите номер заказа, название товара и вес в кг:\n"
    "<code>39 арбуз 5.4</code>\n"
    "Можно несколько строк:\n"
    "<pre>39, Арбуз, 5,4\n"
    "40, дыня 3.6</pre>\n"
    "Или поменяйте вес в админ-панели."
)

_ORDER_LINE_RE = re.compile(r"^\s*#?(?P<order_id>\d+)\s*[,;:\-]?\s*(?P<body>.+?)\s*$")
_TRAILING_WEIGHT_BLOCK_RE = re.compile(
    r"(?P<weights>(?:\d+(?:[.,]\d+)?\s*(?:кг|kg)?\s*(?:[+/]\s*|\s+)?)+)\s*$",
    re.IGNORECASE,
)
_WEIGHT_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

STATUS_FROM_CB = {
    "ACC": "ACCEPTED",
    "DON": "DONE",
    "CAN": "CANCELLED",
    "PAY": "PAID",
}

STATUS_RU = {
    "CREATED": "Принят",
    "ACCEPTED": "Собран",
    "COOKING": "Собран",
    "DELIVERY": "Собран",
    "DONE": "Завершён",
    "CANCELLED": "Отменён",
}


def _actor_name(user: Any) -> str:
    if user and getattr(user, "username", None):
        return f"@{user.username}"
    return f"id:{getattr(user, 'id', '—')}"


def _normalize_product_name(value: str) -> str:
    text = value.lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return " ".join(text.split())


def _format_kg(grams: int) -> str:
    text = format((Decimal(grams) / Decimal("1000")).normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _strip_weight_unit_price(text: str) -> str:
    text = re.sub(
        r"\s*·\s*\d+(?:[.,]\d+)?\s*₽/кг\s*·\s*",
        " · ",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"\s*·\s*\d+(?:[.,]\d+)?\s*₽/кг\b",
        "",
        text,
        flags=re.IGNORECASE,
    )


def _parse_weight_grams(raw: str) -> int | None:
    try:
        kg = Decimal(raw.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    grams = int((kg * Decimal("1000")).to_integral_value())
    if grams <= 0 or grams > 100_000:
        return None
    return grams


def _parse_weight_line(line: str) -> tuple[dict[str, Any] | None, str | None]:
    match = _ORDER_LINE_RE.match(line)
    if not match:
        return None, "строка должна начинаться с номера заказа"

    body = match.group("body").strip()
    weight_match = _TRAILING_WEIGHT_BLOCK_RE.search(body)
    if not weight_match:
        return None, "не нашёл вес в конце строки"

    product_name = body[: weight_match.start()].strip(" ,;:-")
    if not product_name:
        return None, "не нашёл название товара"

    weights: list[int] = []
    for number_match in _WEIGHT_NUMBER_RE.finditer(weight_match.group("weights")):
        grams = _parse_weight_grams(number_match.group(0))
        if grams is None:
            return None, "вес должен быть в кг, например 5.4"
        weights.append(grams)

    if not weights:
        return None, "не нашёл вес"

    return {
        "order_id": int(match.group("order_id")),
        "product_name": product_name,
        "weights": weights,
    }, None


def _find_weight_position(
    positions: list[dict[str, Any]],
    product_query: str,
) -> tuple[dict[str, Any] | None, str | None]:
    weighted_positions = [
        position
        for position in positions
        if bool(position.get("mealRequiresFinalWeight"))
    ]
    if not weighted_positions:
        return None, "в заказе нет товаров с финальным весом"

    normalized_query = _normalize_product_name(product_query)
    if not normalized_query:
        return None, "не нашёл название товара"

    def position_name(position: dict[str, Any]) -> str:
        return str(position.get("mealName") or f"товар #{position.get('mealId')}")

    exact = [
        position
        for position in weighted_positions
        if _normalize_product_name(position_name(position)) == normalized_query
    ]
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        names = ", ".join(position_name(position) for position in exact)
        return None, f"нашёл несколько совпадений: {names}"

    contains = [
        position
        for position in weighted_positions
        if normalized_query in _normalize_product_name(position_name(position))
        or _normalize_product_name(position_name(position)) in normalized_query
    ]
    if len(contains) == 1:
        return contains[0], None
    if len(contains) > 1:
        names = ", ".join(position_name(position) for position in contains)
        return None, f"нашёл несколько похожих товаров: {names}"

    scored = sorted(
        (
            (
                SequenceMatcher(
                    None,
                    normalized_query,
                    _normalize_product_name(position_name(position)),
                ).ratio(),
                position,
            )
            for position in weighted_positions
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if scored and scored[0][0] >= 0.68:
        return scored[0][1], None

    names = ", ".join(position_name(position) for position in weighted_positions)
    return None, f"не нашёл товар «{product_query}». В заказе есть: {names}"


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
                positions_block.append(_strip_weight_unit_price(ln))
                continue
            in_positions = False
        if ln.startswith("💬 "):
            comment_line = ln
            continue
        if (
            "Статус ещё не меняли" in ln
            or "Статус изменил:" in ln
            or "Обновил:" in ln
            or "Выберите статус ниже" in ln
        ):
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
                headers={"X-Market-Bot-Auth": token},
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
        await query.answer("Не задан MARKET_INTERNAL_API_SECRET", show_alert=True)
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
                        "X-Market-Internal-Secret": INTERNAL_API_SECRET,
                        "X-Market-Actor-Name": (
                            f"@{query.from_user.username}" if query.from_user and query.from_user.username
                            else f"id:{query.from_user.id if query.from_user else '—'}"
                        ),
                        "Content-Type": "application/json",
                    },
                    json={"isPaid": True},
                )
            else:
                r = await client.patch(
                    f"{API_BASE}/orders/{order_id}/status",
                    headers={
                        "X-Market-Internal-Secret": INTERNAL_API_SECRET,
                        "X-Market-Actor-Name": (
                            f"@{query.from_user.username}" if query.from_user and query.from_user.username
                            else f"id:{query.from_user.id if query.from_user else '—'}"
                        ),
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


@router.message(F.text)
async def order_weight_text(message: Message):
    text = (message.text or "").strip()
    if not text or not re.match(r"^\s*#?\d", text):
        return
    if not INTERNAL_API_SECRET:
        await message.answer("Не задан MARKET_INTERNAL_API_SECRET. Вес можно поменять в админ-панели.")
        return

    commands: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    for raw_line in re.split(r"\n+|;\s*(?=#?\d+\b)", text):
        line = raw_line.strip()
        if not line:
            continue
        command, error = _parse_weight_line(line)
        if command:
            commands.append(command)
        else:
            parse_errors.append(f"«{html.escape(line)}»: {html.escape(error or 'неизвестная ошибка')}")

    if not commands:
        await message.answer(WEIGHT_COMMAND_HELP)
        return

    actor = _actor_name(message.from_user)
    headers = {
        "X-Market-Internal-Secret": INTERNAL_API_SECRET,
        "X-Market-Actor-Name": actor,
        "Content-Type": "application/json",
    }
    successes: list[str] = []
    api_errors: list[str] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for command in commands:
            order_id = int(command["order_id"])
            product_name = str(command["product_name"])
            weights = list(command["weights"])

            order_response = await client.get(
                f"{API_BASE}/orders/{order_id}",
                headers={"X-Market-Internal-Secret": INTERNAL_API_SECRET},
            )
            if order_response.status_code == 404:
                api_errors.append(f"№{order_id}: заказ не найден")
                continue
            if order_response.status_code != 200:
                api_errors.append(f"№{order_id}: ошибка API {order_response.status_code}")
                continue
            order_payload = order_response.json()
            if str(order_payload.get("status") or "") == "CANCELLED":
                api_errors.append(f"№{order_id}: заказ отменён, вес не менял")
                continue

            positions_response = await client.get(
                f"{API_BASE}/order-positions",
                params={"orderId": order_id},
                headers={"X-Market-Internal-Secret": INTERNAL_API_SECRET},
            )
            if positions_response.status_code != 200:
                api_errors.append(f"№{order_id}: не получил позиции заказа")
                continue

            position, match_error = _find_weight_position(positions_response.json(), product_name)
            if not position:
                api_errors.append(f"№{order_id}: {html.escape(match_error or 'товар не найден')}")
                continue

            position_id = int(position.get("id") or 0)
            quantity = int(position.get("quantity") or 1)
            if position_id <= 0:
                api_errors.append(f"№{order_id}: у позиции нет ID")
                continue

            if len(weights) > 1:
                if len(weights) != quantity:
                    api_errors.append(
                        f"№{order_id}: для «{html.escape(str(position.get('mealName') or product_name))}» "
                        f"нужно {quantity} значений веса или один общий вес"
                    )
                    continue
                patch_response = await client.patch(
                    f"{API_BASE}/order-positions/orders/{order_id}/final-weights",
                    headers=headers,
                    json={
                        "positions": [
                            {
                                "positionId": position_id,
                                "finalWeightGramsList": weights,
                            }
                        ]
                    },
                )
            else:
                patch_response = await client.patch(
                    f"{API_BASE}/order-positions/{position_id}/final-weight",
                    headers=headers,
                    json={"finalWeightGrams": weights[0]},
                )

            if patch_response.status_code != 200:
                detail = ""
                try:
                    payload = patch_response.json()
                    detail = str(payload.get("detail") or "")
                except Exception:
                    detail = patch_response.text[:120]
                suffix = f": {html.escape(detail)}" if detail else ""
                api_errors.append(f"№{order_id}: не сохранил вес{suffix}")
                continue

            weight_text = " + ".join(_format_kg(weight) for weight in weights)
            successes.append(
                f"№{order_id} · {html.escape(str(position.get('mealName') or product_name))} — {weight_text} кг"
            )

    lines: list[str] = []
    if successes:
        lines.append("<b>Вес обновлён</b>")
        lines.extend(f"• {item}" for item in successes)
    all_errors = [*parse_errors, *api_errors]
    if all_errors:
        if lines:
            lines.append("")
        lines.append("<b>Не получилось</b>")
        lines.extend(f"• {error}" for error in all_errors)
        lines.append("")
        lines.append(WEIGHT_COMMAND_HELP)

    await message.answer("\n".join(lines))
