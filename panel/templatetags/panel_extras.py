"""Panel shablonlari uchun filtrlar."""
import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def translations_for(form, language):
    """Formadagi ma'lum tildagi tarjima maydonlarini qaytaradi."""
    getter = getattr(form, "translation_fields", None)
    return getter(language) if getter else []


@register.filter
def money(value):
    """1234567 -> '1 234 567'"""
    try:
        return f"{float(value):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


@register.filter
def filesize(value):
    """Baytni o'qilishi qulay ko'rinishga keltiradi."""
    try:
        size = float(value or 0)
    except (TypeError, ValueError):
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return "—"


@register.filter
def duration(seconds):
    try:
        total = int(seconds or 0)
    except (TypeError, ValueError):
        return "—"
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@register.filter
def jsonify(value):
    """Python ro'yxatini JSON matnga aylantiradi.

    Natija HTML atributiga qo'yiladi, shuning uchun mark_safe QILINMAYDI —
    Django qo'shtirnoqlarni o'zi ekranlaydi, brauzer esa qayta o'qiydi.
    """
    return json.dumps(value, ensure_ascii=False)


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.simple_tag(takes_context=True)
def query_string(context, **kwargs):
    """Joriy GET parametrlarini saqlab, ba'zilarini almashtiradi."""
    request = context.get("request")
    params = request.GET.copy() if request else {}
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    params.pop("page", None)
    encoded = params.urlencode() if hasattr(params, "urlencode") else ""
    return mark_safe(encoded)
