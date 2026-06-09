from __future__ import annotations


def normalize_phone_to_storage(phone: str) -> str | None:
    """Храним телефон цифрами; российские номера приводим к 7XXXXXXXXXX."""
    if not phone or not str(phone).strip():
        return None
    digits = "".join(c for c in str(phone) if c.isdigit())
    if len(digits) == 10:
        return "7" + digits
    if len(digits) == 11 and digits[0] == "7":
        return digits
    if len(digits) == 11 and digits[0] == "8":
        return "7" + digits[1:]
    if 6 <= len(digits) <= 15:
        return digits
    return None


def normalize_ru_phone_to_storage(phone: str) -> str | None:
    """Строгая нормализация российского номера для заказов и staff-поиска."""
    if not phone or not str(phone).strip():
        return None
    digits = "".join(c for c in str(phone) if c.isdigit())
    if len(digits) == 10 and digits[0] == "9":
        return "7" + digits
    if len(digits) == 11 and digits[0] == "7":
        return digits
    if len(digits) == 11 and digits[0] == "8":
        return "7" + digits[1:]
    return None


def is_proper_registered_phone(phone: str | None) -> bool:
    if not phone or phone.startswith("tg-"):
        return False
    return normalize_phone_to_storage(phone) is not None


def is_russian_order_phone(phone: str | None) -> bool:
    if not phone or phone.startswith("tg-"):
        return False
    return normalize_ru_phone_to_storage(phone) is not None
