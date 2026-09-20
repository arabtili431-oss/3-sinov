"""To'lov havolalarini tayyorlash."""
import base64
from decimal import Decimal

from django.conf import settings


def payme_checkout_url(payment, return_url=""):
    """Payme checkout havolasi.

    Format: https://checkout.paycom.uz/<base64("m=...;ac.order_id=...;a=<tiyin>;c=<return>")>
    """
    if not settings.PAYME_MERCHANT_ID:
        return ""
    amount_tiyin = int(Decimal(payment.amount) * 100)
    parts = [
        f"m={settings.PAYME_MERCHANT_ID}",
        f"ac.order_id={payment.reference}",
        f"a={amount_tiyin}",
    ]
    if return_url:
        parts.append(f"c={return_url}")
    encoded = base64.b64encode(";".join(parts).encode()).decode()
    return f"{settings.PAYME_CHECKOUT_URL}/{encoded}"


def click_checkout_url(payment, return_url=""):
    """Click to'lov havolasi."""
    if not (settings.CLICK_SERVICE_ID and settings.CLICK_MERCHANT_ID):
        return ""
    url = (
        f"{settings.CLICK_CHECKOUT_URL}"
        f"?service_id={settings.CLICK_SERVICE_ID}"
        f"&merchant_id={settings.CLICK_MERCHANT_ID}"
        f"&amount={payment.amount}"
        f"&transaction_param={payment.reference}"
    )
    if return_url:
        url += f"&return_url={return_url}"
    return url


def checkout_links(payment, request=None):
    """Ikkala tizim uchun havolalarni qaytaradi."""
    return_url = ""
    if request is not None:
        return_url = request.build_absolute_uri("/tolov/natija/")
    return {
        "payme": payme_checkout_url(payment, return_url),
        "click": click_checkout_url(payment, return_url),
        "reference": payment.reference,
        "amount": str(payment.amount),
    }
