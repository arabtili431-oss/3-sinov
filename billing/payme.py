"""Payme Merchant API (JSON-RPC) — kassa serveri bilan ishlash.

Payme serveri bizga so'rov yuboradi, biz javob qaytaramiz.
Hujjat: https://developer.help.paycom.uz/metody-merchant-api/
"""
import base64
import logging
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .models import Payment

logger = logging.getLogger(__name__)

# Xato kodlari
ERROR_INVALID_AMOUNT = -31001
ERROR_TRANSACTION_NOT_FOUND = -31003
ERROR_CANT_PERFORM = -31008
ERROR_CANT_CANCEL = -31007
ERROR_INVALID_ACCOUNT = -31050
ERROR_INSUFFICIENT_PRIVILEGE = -32504
ERROR_METHOD_NOT_FOUND = -32601

# Tranzaksiya holatlari (Payme terminologiyasi)
STATE_CREATED = 1
STATE_COMPLETED = 2
STATE_CANCELLED = -1
STATE_CANCELLED_AFTER_COMPLETE = -2

TIMEOUT_MS = 12 * 60 * 60 * 1000  # 12 soat


def _error(code, message, data=None):
    return {"error": {"code": code, "message": {"uz": message, "ru": message, "en": message},
                      "data": data}}


def _ms(dt):
    return int(dt.timestamp() * 1000) if dt else 0


def check_auth(request) -> bool:
    """Basic auth: login 'Paycom', parol — kassa kaliti."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:]).decode()
        login, _, password = decoded.partition(":")
    except Exception:
        return False
    valid_keys = [k for k in (settings.PAYME_KEY, settings.PAYME_TEST_KEY) if k]
    return login == "Paycom" and password in valid_keys


def _find_payment(params):
    """account.order_id bo'yicha to'lovni topadi."""
    account = params.get("account") or {}
    reference = account.get("order_id") or account.get("reference")
    if not reference:
        return None
    return Payment.objects.filter(reference=reference).first()


def _transaction_body(payment):
    return {
        "create_time": payment.create_time or _ms(payment.created_at),
        "perform_time": payment.perform_time,
        "cancel_time": payment.cancel_time,
        "transaction": str(payment.pk),
        "state": _state_of(payment),
        "reason": payment.cancel_reason,
    }


def _state_of(payment):
    if payment.state == Payment.STATE_PAID:
        return STATE_COMPLETED
    if payment.state == Payment.STATE_CANCELLED:
        return STATE_CANCELLED_AFTER_COMPLETE if payment.perform_time else STATE_CANCELLED
    return STATE_CREATED


# ------------------------------------------------------------------ Metodlar
def check_perform_transaction(params):
    payment = _find_payment(params)
    if payment is None:
        return _error(ERROR_INVALID_ACCOUNT, "Buyurtma topilmadi", "order_id")
    if payment.state == Payment.STATE_PAID:
        return _error(ERROR_CANT_PERFORM, "Buyurtma allaqachon to'langan")
    amount = Decimal(params.get("amount", 0)) / 100
    if amount != Decimal(payment.amount):
        return _error(ERROR_INVALID_AMOUNT, "Summa noto'g'ri")
    return {"result": {"allow": True}}


def create_transaction(params):
    payment = _find_payment(params)
    if payment is None:
        return _error(ERROR_INVALID_ACCOUNT, "Buyurtma topilmadi", "order_id")

    external_id = params.get("id", "")
    amount = Decimal(params.get("amount", 0)) / 100

    # Shu tranzaksiya allaqachon yaratilganmi?
    if payment.external_id and payment.external_id != external_id:
        return _error(ERROR_CANT_PERFORM, "Buyurtma uchun boshqa tranzaksiya ochilgan")
    if amount != Decimal(payment.amount):
        return _error(ERROR_INVALID_AMOUNT, "Summa noto'g'ri")
    if payment.state == Payment.STATE_CANCELLED:
        return _error(ERROR_CANT_PERFORM, "Tranzaksiya bekor qilingan")

    if not payment.external_id:
        payment.external_id = external_id
        payment.provider = Payment.PROVIDER_PAYME
        payment.state = Payment.STATE_HOLD
        payment.create_time = params.get("time") or _ms(timezone.now())
        payment.raw = params
        payment.save(update_fields=["external_id", "provider", "state", "create_time", "raw"])

    return {"result": {
        "create_time": payment.create_time,
        "transaction": str(payment.pk),
        "state": _state_of(payment),
    }}


def perform_transaction(params):
    payment = Payment.objects.filter(external_id=params.get("id", "")).first()
    if payment is None:
        return _error(ERROR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")

    if payment.state == Payment.STATE_PAID:
        return {"result": {"transaction": str(payment.pk), "perform_time": payment.perform_time,
                           "state": STATE_COMPLETED}}
    if payment.state == Payment.STATE_CANCELLED:
        return _error(ERROR_CANT_PERFORM, "Tranzaksiya bekor qilingan")

    # Vaqt tugaganmi?
    now = _ms(timezone.now())
    if payment.create_time and now - payment.create_time > TIMEOUT_MS:
        payment.mark_cancelled(reason=4)
        return _error(ERROR_CANT_PERFORM, "Tranzaksiya vaqti tugagan")

    payment.mark_paid()
    return {"result": {"transaction": str(payment.pk), "perform_time": payment.perform_time,
                       "state": STATE_COMPLETED}}


def cancel_transaction(params):
    payment = Payment.objects.filter(external_id=params.get("id", "")).first()
    if payment is None:
        return _error(ERROR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")

    if payment.state != Payment.STATE_CANCELLED:
        payment.mark_cancelled(reason=params.get("reason"))

    return {"result": {"transaction": str(payment.pk), "cancel_time": payment.cancel_time,
                       "state": _state_of(payment)}}


def check_transaction(params):
    payment = Payment.objects.filter(external_id=params.get("id", "")).first()
    if payment is None:
        return _error(ERROR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")
    return {"result": _transaction_body(payment)}


def get_statement(params):
    start, end = params.get("from", 0), params.get("to", 0)
    payments = Payment.objects.filter(
        provider=Payment.PROVIDER_PAYME, create_time__gte=start, create_time__lte=end,
    ).exclude(external_id="")
    return {"result": {"transactions": [
        {
            "id": p.external_id,
            "time": p.create_time,
            "amount": int(Decimal(p.amount) * 100),
            "account": {"order_id": p.reference},
            "create_time": p.create_time,
            "perform_time": p.perform_time,
            "cancel_time": p.cancel_time,
            "transaction": str(p.pk),
            "state": _state_of(p),
            "reason": p.cancel_reason,
        }
        for p in payments
    ]}}


METHODS = {
    "CheckPerformTransaction": check_perform_transaction,
    "CreateTransaction": create_transaction,
    "PerformTransaction": perform_transaction,
    "CancelTransaction": cancel_transaction,
    "CheckTransaction": check_transaction,
    "GetStatement": get_statement,
}


def handle(request, payload):
    """JSON-RPC so'rovini qayta ishlaydi."""
    if not check_auth(request):
        return {"error": {"code": ERROR_INSUFFICIENT_PRIVILEGE,
                          "message": {"uz": "Ruxsat yo'q", "ru": "Нет доступа", "en": "Forbidden"}}}

    method = payload.get("method")
    params = payload.get("params") or {}
    handler = METHODS.get(method)
    if handler is None:
        return _error(ERROR_METHOD_NOT_FOUND, f"Metod topilmadi: {method}")

    try:
        return handler(params)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Payme metodida xato: %s", method)
        return _error(ERROR_CANT_PERFORM, str(exc))
