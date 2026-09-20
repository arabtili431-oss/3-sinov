"""Yordamchi funksiyalar: telefon raqamni normallashtirish va kod generatsiyasi."""
import re
import secrets

UZ_PHONE_RE = re.compile(r"^\+998(9[0-9]|8[8]|3[3]|7[1]|2[0]|1[0-9]|5[05]|6[26]|9[89])\d{7}$")


def normalize_phone(raw: str) -> str:
    """Har qanday ko'rinishdagi raqamni +998XXXXXXXXX formatiga keltiradi.

    Masalan: "(90) 123-45-67", "90 123 45 67", "998901234567" -> "+998901234567"
    """
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("998"):
        digits = digits[3:]
    elif digits.startswith("8") and len(digits) == 10:
        digits = digits[1:]
    if len(digits) != 9:
        return ""
    return "+998" + digits


def is_valid_uz_phone(phone: str) -> bool:
    """+998XXXXXXXXX formatidagi raqam to'g'riligini tekshiradi."""
    return bool(phone) and len(phone) == 13 and phone.startswith("+998") and phone[4:].isdigit()


def generate_code(length: int = 5) -> str:
    """Tasodifiy raqamli tasdiqlash kodi."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def mask_phone(phone: str) -> str:
    """+998901234567 -> +998 90 *** ** 67"""
    if not phone or len(phone) != 13:
        return phone
    return f"{phone[:4]} {phone[4:6]} *** ** {phone[11:]}"
