from __future__ import annotations


def normalize_ru_phone_to_storage(phone: str) -> str | None:
    """Храним российский номер как 11 цифр с 7 в начале."""
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
    norm = normalize_ru_phone_to_storage(phone)
    return norm is not None and len(norm) == 11
