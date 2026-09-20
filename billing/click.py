"""Click Merchant API — Prepare / Complete.

Click serveri bizga POST yuboradi (form-data), biz JSON qaytaramiz.
Hujjat: https://docs.click.uz/click-api-request/
"""
import hashlib
import logging
from decimal import Decimal

from django.conf import settings

from .models import Payment

logger = logging.getLogger(__name__)

# Click xato kodlari
SUCCESS = 0
ERROR_SIGN_CHECK = -1
ERROR_INCORRECT_AMOUNT = -2
ERROR_ACTION_NOT_FOUND = -3
ERROR_ALREADY_PAID = -4
ERROR_USER_NOT_FOUND = -5
ERROR_TRANSACTION_NOT_FOUND = -6
ERROR_BAD_REQUEST = -8
ERROR_TRANSACTION_CANCELLED = -9

ACTION_PREPARE = "0"
ACTION_COMPLETE = "1"


def _make_signature(data, action):
    """MD5 imzosi. Complete uchun merchant_prepare_id ham qatnashadi."""
    parts = [
        data.get("click_trans_id", ""),
        data.get("service_id", ""),
        settings.CLICK_SECRET_KEY,
        data.get("merchant_trans_id", ""),
    ]
    if action == ACTION_COMPLETE:
        parts.append(data.get("merchant_prepare_id", ""))
    parts += [data.get("amount", ""), data.get("action", ""), data.get("sign_time", "")]
    return hashlib.md5("".join(str(p) for p in parts).encode()).hexdigest()


def _response(code, note, extra=None):
    body = {"error": code, "error_note": note}
    if extra:
        body.update(extra)
    return body


def _verify(data):
    """Imzo va summani tekshiradi; xato bo'lsa javob, aks holda (payment, None)."""
    action = str(data.get("action", ""))
    expected = _make_signature(data, action)
    if expected != data.get("sign_string", ""):
        return None, _response(ERROR_SIGN_CHECK, "Imzo noto'g'ri")

    payment = Payment.objects.filter(reference=data.get("merchant_trans_id", "")).first()
    if payment is None:
        return None, _response(ERROR_USER_NOT_FOUND, "Buyurtma topilmadi")

    try:
        amount = Decimal(str(data.get("amount", "0")))
    except Exception:
        return None, _response(ERROR_INCORRECT_AMOUNT, "Summa noto'g'ri")
    if abs(amount - Decimal(payment.amount)) > Decimal("0.01"):
        return None, _response(ERROR_INCORRECT_AMOUNT, "Summa mos kelmadi")

    return payment, None


def prepare(data):
    """1-bosqich: to'lovni tayyorlash."""
    payment, error = _verify(data)
    if error:
        return error

    if payment.state == Payment.STATE_PAID:
        return _response(ERROR_ALREADY_PAID, "Allaqachon to'langan")
    if payment.state == Payment.STATE_CANCELLED:
        return _response(ERROR_TRANSACTION_CANCELLED, "Tranzaksiya bekor qilingan")

    payment.provider = Payment.PROVIDER_CLICK
    payment.external_id = str(data.get("click_trans_id", ""))
    payment.state = Payment.STATE_HOLD
    payment.raw = dict(data)
    payment.save(update_fields=["provider", "external_id", "state", "raw"])

    return _response(SUCCESS, "Success", {
        "click_trans_id": data.get("click_trans_id"),
        "merchant_trans_id": payment.reference,
        "merchant_prepare_id": payment.pk,
    })


def complete(data):
    """2-bosqich: to'lovni yakunlash."""
    payment, error = _verify(data)
    if error:
        return error

    if str(payment.pk) != str(data.get("merchant_prepare_id", "")):
        return _response(ERROR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")

    # Click o'zi bekor qilgan bo'lsa
    if str(data.get("error", "0")) not in ("0", ""):
        payment.mark_cancelled(reason=int(data.get("error", -1)))
        return _response(ERROR_TRANSACTION_CANCELLED, "Tranzaksiya bekor qilindi")

    if payment.state == Payment.STATE_PAID:
        return _response(ERROR_ALREADY_PAID, "Allaqachon to'langan")

    payment.mark_paid()
    return _response(SUCCESS, "Success", {
        "click_trans_id": data.get("click_trans_id"),
        "merchant_trans_id": payment.reference,
        "merchant_confirm_id": payment.pk,
    })


def handle(data):
    action = str(data.get("action", ""))
    if action == ACTION_PREPARE:
        return prepare(data)
    if action == ACTION_COMPLETE:
        return complete(data)
    return _response(ERROR_ACTION_NOT_FOUND, "Amal topilmadi")
