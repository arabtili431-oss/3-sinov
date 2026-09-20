"""Telegram Bot API bilan ishlash (kod yuborish)."""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _call(method: str, payload: dict, timeout: int = 10):
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN sozlanmagan — so'rov yuborilmadi: %s", method)
        return None
    try:
        resp = requests.post(API_BASE.format(token=token, method=method), json=payload, timeout=timeout)
        data = resp.json()
        if not data.get("ok"):
            logger.error("Telegram xatosi (%s): %s", method, data)
        return data
    except requests.RequestException as exc:
        logger.error("Telegram bilan bog'lanib bo'lmadi (%s): %s", method, exc)
        return None


def send_message(chat_id: int, text: str, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _call("sendMessage", payload)


def send_code(chat_id: int, code: str, full_name: str = "", purpose: str = "register"):
    """Foydalanuvchiga tasdiqlash kodini yuboradi."""
    salom = f"Assalomu alaykum, {full_name}!\n\n" if full_name else "Assalomu alaykum!\n\n"
    sabab = {
        "register": "<b>VECTOR</b> platformasida ro'yxatdan o'tishni yakunlash uchun",
        "login": "<b>VECTOR</b> platformasiga kirish uchun",
        "reset": "<b>VECTOR</b> platformasida parolni tiklash uchun",
    }.get(purpose, "<b>VECTOR</b> platformasi uchun")
    text = (
        f"{salom}"
        f"{sabab} tasdiqlash kodingiz:\n\n"
        f"<code>{code}</code>\n\n"
        f"Kod {settings.OTP_TTL_SECONDS // 60} daqiqa davomida amal qiladi.\n"
        f"\u26a0\ufe0f Bu kodni hech kimga bermang. VECTOR xodimlari kodni hech qachon so'ramaydi."
    )
    return send_message(chat_id, text, reply_markup={"remove_keyboard": True})


def bot_start_url(start_token: str) -> str:
    """Deep-link: botni ochib, /start <token> yuboradi."""
    username = (settings.TELEGRAM_BOT_USERNAME or "").lstrip("@")
    if not username:
        return ""
    return f"https://t.me/{username}?start={start_token}"
