"""Panel uchun til aniqlash: standart til — o'zbekcha.

Brauzerning Accept-Language sarlavhasi emas, foydalanuvchi tanlovi ustun turadi.
"""
from django.conf import settings
from django.utils import translation


class DefaultLanguageMiddleware:
    """Cookie yoki sessiyada til tanlanmagan bo'lsa, o'zbekchani qo'yadi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        chosen = (
            request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
            or request.session.get("_language") if hasattr(request, "session") else None
        )
        if not chosen:
            # LocaleMiddleware brauzer tilini olmasligi uchun sarlavhani almashtiramiz
            request.META["HTTP_ACCEPT_LANGUAGE"] = settings.LANGUAGE_CODE
        return self.get_response(request)
