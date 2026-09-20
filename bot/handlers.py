"""Telegram bot mantiqi: /start deep-link, kontakt qabul qilish, kod yuborish."""
import logging

from django.utils import timezone

from accounts.models import TelegramVerification, User
from accounts.telegram import send_code, send_message
from accounts.utils import normalize_phone

logger = logging.getLogger(__name__)

SHARE_CONTACT_KEYBOARD = {
    "keyboard": [[{"text": "📱 Telefon raqamni ulashish", "request_contact": True}]],
    "resize_keyboard": True,
    "one_time_keyboard": True,
}

TXT_WELCOME = (
    "Assalomu alaykum! 👋\n\n"
    "Bu <b>VECTOR</b> platformasining rasmiy tasdiqlash boti.\n\n"
    "Ro'yxatdan o'tishni yakunlash uchun quyidagi tugma orqali "
    "telefon raqamingizni ulashing."
)
TXT_NO_TOKEN = (
    "Assalomu alaykum! 👋\n\n"
    "Bu <b>VECTOR</b> tasdiqlash boti.\n\n"
    "Tasdiqlashni boshlash uchun saytdagi <b>«Telegram orqali tasdiqlash»</b> "
    "tugmasini bosing."
)
TXT_WELCOME_RESET = (
    "Assalomu alaykum!\n\n"
    "Parolni tiklash so'rovi qabul qilindi.\n\n"
    "Davom etish uchun quyidagi tugma orqali telefon raqamingizni ulashing."
)
TXT_EXPIRED = "⌛️ Bu havolaning muddati tugagan. Iltimos, saytda qaytadan urinib ko'ring."
TXT_WRONG_PHONE = (
    "❌ Siz ulashgan raqam saytda kiritilgan raqamga mos kelmadi.\n\n"
    "Saytda <b>{phone}</b> raqami kiritilgan. Xuddi shu raqamga ega "
    "Telegram akkauntdan foydalaning yoki saytda raqamni to'g'irlang."
)
TXT_NOT_OWN = "❌ Iltimos, tugma orqali <b>o'zingizning</b> raqamingizni ulashing."


def _active_verification_for_chat(chat_id):
    return (
        TelegramVerification.objects.filter(
            telegram_chat_id=chat_id, is_used=False, expires_at__gt=timezone.now()
        )
        .select_related("user")
        .order_by("-created_at")
        .first()
    )


def handle_start(chat_id, token, from_user):
    """/start [token] buyrug'i."""
    if not token:
        send_message(chat_id, TXT_NO_TOKEN)
        return

    verification = (
        TelegramVerification.objects.filter(start_token=token, is_used=False)
        .select_related("user")
        .first()
    )
    if verification is None or verification.is_expired:
        send_message(chat_id, TXT_EXPIRED)
        return

    verification.telegram_chat_id = chat_id
    verification.save(update_fields=["telegram_chat_id"])

    # Foydalanuvchi shu botga avval ham shu raqam bilan ulangan bo'lsa — kodni darhol yuboramiz.
    known = User.objects.filter(telegram_id=chat_id, phone=verification.phone).first()
    if known:
        code = verification.issue_code(chat_id=chat_id)
        send_code(chat_id, code, known.full_name, verification.purpose)
        return

    welcome = TXT_WELCOME_RESET if verification.purpose == TelegramVerification.PURPOSE_RESET else TXT_WELCOME
    send_message(chat_id, welcome, reply_markup=SHARE_CONTACT_KEYBOARD)


def handle_contact(chat_id, contact, from_user):
    """Foydalanuvchi kontaktini ulashganda."""
    verification = _active_verification_for_chat(chat_id)
    if verification is None:
        send_message(chat_id, TXT_NO_TOKEN)
        return

    # Boshqa odamning kontaktini yuborishga yo'l qo'ymaymiz
    if contact.get("user_id") and from_user.get("id") and contact["user_id"] != from_user["id"]:
        send_message(chat_id, TXT_NOT_OWN, reply_markup=SHARE_CONTACT_KEYBOARD)
        return

    phone = normalize_phone(contact.get("phone_number", ""))
    if phone != verification.phone:
        send_message(
            chat_id,
            TXT_WRONG_PHONE.format(phone=verification.phone),
            reply_markup={"remove_keyboard": True},
        )
        return

    user = verification.user or User.objects.filter(phone=phone).first()
    if user:
        username = from_user.get("username") or ""
        update_fields = []
        if username and user.telegram_username != username:
            user.telegram_username = username
            update_fields.append("telegram_username")
        if update_fields:
            user.save(update_fields=update_fields)

    code = verification.issue_code(chat_id=chat_id)
    send_code(chat_id, code, user.full_name if user else "", verification.purpose)


def handle_update(update: dict):
    """Telegramdan kelgan bitta update'ni qayta ishlaydi."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat_id = (message.get("chat") or {}).get("id")
    from_user = message.get("from") or {}
    if not chat_id:
        return

    try:
        if "contact" in message:
            handle_contact(chat_id, message["contact"], from_user)
            return

        text = (message.get("text") or "").strip()
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            token = parts[1].strip() if len(parts) > 1 else ""
            handle_start(chat_id, token, from_user)
            return

        if text in ("/help", "/yordam"):
            send_message(chat_id, TXT_NO_TOKEN)
            return

        # Boshqa har qanday xabar
        verification = _active_verification_for_chat(chat_id)
        if verification and not verification.code_hash:
            send_message(chat_id, TXT_WELCOME, reply_markup=SHARE_CONTACT_KEYBOARD)
        else:
            send_message(chat_id, TXT_NO_TOKEN)
    except Exception:  # noqa: BLE001
        logger.exception("Update qayta ishlashda xato: %s", update)
