from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.restaurant import Restaurant

MSK = ZoneInfo("Europe/Moscow")
DEFAULT_DELIVERY_CUTOFF = "17:00"


def msk_today_utc_naive_bounds() -> tuple[datetime, datetime]:
    """Границы «сегодня» по календарю Москвы в виде naive UTC (для сравнения с created_at в UTC)."""
    now_msk = datetime.now(MSK)
    d = now_msk.date()
    start_msk = datetime(d.year, d.month, d.day, tzinfo=MSK)
    end_msk = start_msk + timedelta(days=1)
    return (
        start_msk.astimezone(timezone.utc).replace(tzinfo=None),
        end_msk.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _parse_hhmm(s: str | None) -> tuple[int, int] | None:
    if not s or not str(s).strip():
        return None
    parts = str(s).strip().split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h, m


def restaurant_accepts_orders_now(rest: Restaurant) -> bool:
    """Маркет принимает заказы круглосуточно; дедлайн влияет только на день доставки."""
    return True


def restaurant_delivery_cutoff(rest: Restaurant) -> str:
    return (rest.orders_accept_to or DEFAULT_DELIVERY_CUTOFF).strip() or DEFAULT_DELIVERY_CUTOFF


def delivery_day_label(rest: Restaurant, now: datetime | None = None) -> str:
    """Сегодня, если заказ оформлен до дедлайна доставки по Москве; иначе завтра."""
    cutoff = _parse_hhmm(restaurant_delivery_cutoff(rest))
    if not cutoff:
        cutoff = _parse_hhmm(DEFAULT_DELIVERY_CUTOFF)
    if not cutoff:
        return "сегодня"
    current = now.astimezone(MSK) if now else datetime.now(MSK)
    current_minutes = current.hour * 60 + current.minute
    cutoff_minutes = cutoff[0] * 60 + cutoff[1]
    return "сегодня" if current_minutes <= cutoff_minutes else "завтра"


def restaurant_accepts_orders_in_window(rest: Restaurant) -> bool:
    """Старое окно приёма заказов оставлено для совместимости, но в checkout не используется."""
    a = _parse_hhmm(rest.orders_accept_from)
    b = _parse_hhmm(rest.orders_accept_to)
    if not a or not b:
        return True
    now = datetime.now(MSK)
    cur = now.hour * 60 + now.minute
    start = a[0] * 60 + a[1]
    end = b[0] * 60 + b[1]
    if start <= end:
        return start <= cur <= end
    return cur >= start or cur <= end
