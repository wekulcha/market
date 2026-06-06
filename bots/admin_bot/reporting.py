from __future__ import annotations

from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any
import html


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _money(value: Any) -> str:
    amount = _to_decimal(value)
    normalized = amount.quantize(Decimal("0.01"))
    if normalized == normalized.to_integral():
        return f"{int(normalized)} ₽"
    text = format(normalized.normalize(), "f").rstrip("0").rstrip(".")
    return f"{text} ₽"


def _positions_lines(section: dict[str, Any]) -> list[str]:
    positions = section.get("positions") or []
    if not positions:
        return ["Позиции: пока нет."]
    lines = ["Позиции (без отменённых заказов):"]
    for position in positions:
        meal_name = html.escape(str(position.get("mealName") or "Без названия"))
        lines.append(
            "• "
            f"{meal_name} × {position.get('quantity', 0)}"
            f" — {_money(position.get('totalPrice'))}"
        )
    return lines


def _section_lines(section: dict[str, Any], title: str) -> list[str]:
    lines = [
        f"<b>{html.escape(title)}</b>",
        f"Заказов: {section.get('ordersCount', 0)}",
        f"Сумма: {_money(section.get('revenue'))}",
        f"Средний чек: {_money(section.get('avgCheck'))}",
        (
            "Оплачено: "
            f"{section.get('paidOrdersCount', 0)}"
            f" на {_money(section.get('paidRevenue'))}"
        ),
        (
            "Не оплачено: "
            f"{section.get('unpaidOrdersCount', 0)}"
            f" на {_money(section.get('unpaidRevenue'))}"
        ),
        (
            "Отменено: "
            f"{section.get('cancelledOrdersCount', 0)}"
            f" на {_money(section.get('cancelledRevenue'))}"
        ),
        f"Сумма товаров: {_money(section.get('itemsTotal'))}",
    ]
    if section.get("orderType") == "DELIVERY":
        assigned = int(section.get("courierAssignedOrdersCount", 0) or 0)
        total_orders = int(section.get("ordersCount", 0) or 0)
        lines.append(f"Курьер назначен: {assigned} из {total_orders}")
        lines.append(f"Доставка: {_money(section.get('deliveryFeeTotal'))}")
    else:
        lines.append(f"Доставка: {_money(section.get('deliveryFeeTotal'))}")
    lines.append(f"Сервисный сбор: {_money(section.get('serviceFeeTotal'))}")
    lines.append("")
    lines.extend(_positions_lines(section))
    return lines


def _chunk_lines(lines: list[str], limit: int = 3800) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        addition = len(line) + 1
        if current and current_len + addition > limit:
            chunks.append("\n".join(current).strip())
            current = [line]
            current_len = addition
            continue
        current.append(line)
        current_len += addition

    if current:
        chunks.append("\n".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def build_today_report_messages(summary: dict[str, Any]) -> list[str]:
    restaurants = summary.get("restaurants") or []
    report_date = summary.get("reportDate") or "—"
    timezone = summary.get("timezone") or "Europe/Moscow"

    if not restaurants:
        return [
            "<b>Итоги за сегодня</b>\n"
            "━━━━━━━━━━━━━━\n"
            f"Дата отчёта: {html.escape(str(report_date))} ({html.escape(str(timezone))})\n"
            "Сегодня заказов пока нет."
        ]

    messages: list[str] = []
    header = [
        "<b>Итоги за сегодня</b>",
        "━━━━━━━━━━━━━━",
        f"Дата отчёта: {html.escape(str(report_date))} ({html.escape(str(timezone))})",
        f"Магазинов в отчёте: {len(restaurants)}",
    ]
    messages.append("\n".join(header))

    for restaurant in restaurants:
        lines = [
            f"<b>{html.escape(str(restaurant.get('restaurantName') or 'Магазин'))}</b>",
            "━━━━━━━━━━━━━━",
            f"Всего заказов: {restaurant.get('totalOrdersCount', 0)}",
            f"Общая сумма: {_money(restaurant.get('totalRevenue'))}",
            f"Средний чек: {_money(restaurant.get('avgCheck'))}",
            (
                "Оплачено: "
                f"{restaurant.get('paidOrdersCount', 0)}"
                f" на {_money(restaurant.get('paidRevenue'))}"
            ),
            (
                "Не оплачено: "
                f"{restaurant.get('unpaidOrdersCount', 0)}"
                f" на {_money(restaurant.get('unpaidRevenue'))}"
            ),
            (
                "Отменено: "
                f"{restaurant.get('cancelledOrdersCount', 0)}"
                f" на {_money(restaurant.get('cancelledRevenue'))}"
            ),
            "",
        ]
        lines.extend(_section_lines(restaurant.get("dineIn") or {}, "Заказы на месте"))
        lines.append("")
        lines.extend(_section_lines(restaurant.get("delivery") or {}, "Доставка"))
        messages.extend(_chunk_lines(lines))

    return messages


def build_today_report_pdf(summary: dict[str, Any]) -> bytes | None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        return None

    font_name = "Helvetica"
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ):
        path = Path(candidate)
        if path.exists():
            font_name = "KulchaReportFont"
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(path)))
            except Exception:
                return None
            break

    if font_name == "Helvetica":
        return None

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=32,
        rightMargin=32,
        topMargin=32,
        bottomMargin=32,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "KulchaTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=16,
        leading=20,
        spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "KulchaHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=13,
        leading=16,
        spaceAfter=6,
        spaceBefore=8,
    )
    body_style = ParagraphStyle(
        "KulchaBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10,
        leading=13,
        spaceAfter=3,
    )

    report_date = html.escape(str(summary.get("reportDate") or "—"))
    timezone = html.escape(str(summary.get("timezone") or "Europe/Moscow"))
    story: list[Any] = [
        Paragraph("Итоги за сегодня", title_style),
        Paragraph(f"Дата отчёта: {report_date} ({timezone})", body_style),
        Spacer(1, 6),
    ]

    restaurants = summary.get("restaurants") or []
    if not restaurants:
        story.append(Paragraph("Сегодня заказов пока нет.", body_style))
        doc.build(story)
        return buffer.getvalue()

    for index, restaurant in enumerate(restaurants):
        story.append(
            Paragraph(
                html.escape(str(restaurant.get("restaurantName") or "Магазин")),
                heading_style,
            )
        )
        story.append(
            Paragraph(
                (
                    f"Всего заказов: {restaurant.get('totalOrdersCount', 0)}<br/>"
                    f"Общая сумма: {_money(restaurant.get('totalRevenue'))}<br/>"
                    f"Средний чек: {_money(restaurant.get('avgCheck'))}<br/>"
                    f"Оплачено: {restaurant.get('paidOrdersCount', 0)}"
                    f" на {_money(restaurant.get('paidRevenue'))}<br/>"
                    f"Не оплачено: {restaurant.get('unpaidOrdersCount', 0)}"
                    f" на {_money(restaurant.get('unpaidRevenue'))}<br/>"
                    f"Отменено: {restaurant.get('cancelledOrdersCount', 0)}"
                    f" на {_money(restaurant.get('cancelledRevenue'))}"
                ),
                body_style,
            )
        )
        for title, key in (("Заказы на месте", "dineIn"), ("Доставка", "delivery")):
            section = restaurant.get(key) or {}
            story.append(Paragraph(title, heading_style))
            body_lines = [
                f"Заказов: {section.get('ordersCount', 0)}",
                f"Сумма: {_money(section.get('revenue'))}",
                f"Средний чек: {_money(section.get('avgCheck'))}",
                f"Оплачено: {section.get('paidOrdersCount', 0)} на {_money(section.get('paidRevenue'))}",
                f"Не оплачено: {section.get('unpaidOrdersCount', 0)} на {_money(section.get('unpaidRevenue'))}",
                f"Отменено: {section.get('cancelledOrdersCount', 0)} на {_money(section.get('cancelledRevenue'))}",
                f"Сумма товаров: {_money(section.get('itemsTotal'))}",
                f"Доставка: {_money(section.get('deliveryFeeTotal'))}",
                f"Сервисный сбор: {_money(section.get('serviceFeeTotal'))}",
            ]
            if section.get("orderType") == "DELIVERY":
                body_lines.append(
                    "Курьер назначен: "
                    f"{section.get('courierAssignedOrdersCount', 0)}"
                    f" из {section.get('ordersCount', 0)}"
                )
            story.append(Paragraph("<br/>".join(html.escape(line) for line in body_lines), body_style))
            story.append(Paragraph("Позиции (без отменённых заказов):", body_style))
            positions = section.get("positions") or []
            if not positions:
                story.append(Paragraph("Пока нет.", body_style))
            else:
                for position in positions:
                    story.append(
                        Paragraph(
                            html.escape(
                                f"• {position.get('mealName', 'Без названия')} × {position.get('quantity', 0)}"
                                f" — {_money(position.get('totalPrice'))}"
                            ),
                            body_style,
                        )
                    )
        if index < len(restaurants) - 1:
            story.append(PageBreak())

    doc.build(story)
    return buffer.getvalue()
