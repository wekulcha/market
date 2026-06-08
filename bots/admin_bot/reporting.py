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
        return ["<i>Общие позиции: пока нет.</i>"]
    lines = ["<b>Общие позиции</b> <i>(без отменённых)</i>"]
    for index, position in enumerate(positions, start=1):
        meal_name = html.escape(str(position.get("mealName") or "Без названия"))
        lines.append(
            f"{index}. {meal_name} — "
            f"<b>×{position.get('quantity', 0)}</b>"
            f" · {_money(position.get('totalPrice'))}"
        )
    return lines


def _delivery_lines(section: dict[str, Any]) -> list[str]:
    assigned = int(section.get("courierAssignedOrdersCount", 0) or 0)
    total_orders = int(section.get("ordersCount", 0) or 0)
    lines = [
        "<b>Доставка</b>",
        (
            f"Заказы: <b>{total_orders}</b>"
            f" · сумма <b>{_money(section.get('revenue'))}</b>"
            f" · средний чек {_money(section.get('avgCheck'))}"
        ),
        (
            "Оплачено: "
            f"<b>{section.get('paidOrdersCount', 0)}</b>"
            f" · {_money(section.get('paidRevenue'))}"
        ),
        (
            "Не оплачено: "
            f"<b>{section.get('unpaidOrdersCount', 0)}</b>"
            f" · {_money(section.get('unpaidRevenue'))}"
        ),
        (
            "Отменено: "
            f"<b>{section.get('cancelledOrdersCount', 0)}</b>"
            f" · {_money(section.get('cancelledRevenue'))}"
        ),
        (
            f"Товары: {_money(section.get('itemsTotal'))}"
            f" · доставка: {_money(section.get('deliveryFeeTotal'))}"
            f" · сервис: {_money(section.get('serviceFeeTotal'))}"
        ),
        f"Курьер назначен: {assigned} из {total_orders}",
        "",
    ]
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
        lines.extend(_delivery_lines(restaurant.get("delivery") or {}))
        messages.extend(_chunk_lines(lines))

    return messages


def build_today_report_pdf(summary: dict[str, Any]) -> bytes | None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib import colors
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
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
    small_style = ParagraphStyle(
        "KulchaSmall",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9,
        leading=11,
        spaceAfter=2,
    )

    def table_style() -> TableStyle:
        return TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
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
        summary_rows = [
            ["Показатель", "Значение"],
            ["Всего заказов", str(restaurant.get("totalOrdersCount", 0))],
            ["Общая сумма", _money(restaurant.get("totalRevenue"))],
            ["Средний чек", _money(restaurant.get("avgCheck"))],
            [
                "Оплачено",
                f"{restaurant.get('paidOrdersCount', 0)} · {_money(restaurant.get('paidRevenue'))}",
            ],
            [
                "Не оплачено",
                f"{restaurant.get('unpaidOrdersCount', 0)} · {_money(restaurant.get('unpaidRevenue'))}",
            ],
            [
                "Отменено",
                f"{restaurant.get('cancelledOrdersCount', 0)} · {_money(restaurant.get('cancelledRevenue'))}",
            ],
        ]
        summary_table = Table(summary_rows, colWidths=[170, 300], hAlign="LEFT")
        summary_table.setStyle(table_style())
        story.append(summary_table)
        story.append(Spacer(1, 8))

        section = restaurant.get("delivery") or {}
        story.append(Paragraph("Доставка", heading_style))
        delivery_rows = [
            ["Заказы", str(section.get("ordersCount", 0))],
            ["Сумма", _money(section.get("revenue"))],
            ["Средний чек", _money(section.get("avgCheck"))],
            ["Товары", _money(section.get("itemsTotal"))],
            ["Доставка", _money(section.get("deliveryFeeTotal"))],
            ["Сервисный сбор", _money(section.get("serviceFeeTotal"))],
            [
                "Курьер назначен",
                f"{section.get('courierAssignedOrdersCount', 0)} из {section.get('ordersCount', 0)}",
            ],
        ]
        delivery_table = Table([["Показатель", "Значение"], *delivery_rows], colWidths=[170, 300], hAlign="LEFT")
        delivery_table.setStyle(table_style())
        story.append(delivery_table)
        story.append(Spacer(1, 8))

        story.append(Paragraph("Общие позиции (без отменённых)", heading_style))
        positions = section.get("positions") or []
        if not positions:
            story.append(Paragraph("Пока нет.", body_style))
        else:
            position_rows = [["№", "Позиция", "Кол-во", "Сумма"]]
            for pos_index, position in enumerate(positions, start=1):
                position_rows.append(
                    [
                        str(pos_index),
                        Paragraph(html.escape(str(position.get("mealName", "Без названия"))), small_style),
                        str(position.get("quantity", 0)),
                        _money(position.get("totalPrice")),
                    ]
                )
            positions_table = Table(position_rows, colWidths=[28, 290, 70, 82], hAlign="LEFT")
            positions_table.setStyle(table_style())
            story.append(positions_table)
        if index < len(restaurants) - 1:
            story.append(PageBreak())

    doc.build(story)
    return buffer.getvalue()
