"""Har bir sahifaga uzatiladigan umumiy ma'lumotlar."""
from django.conf import settings
from django.utils.translation import get_language

from core.i18n import LANGUAGES


def panel_context(request):
    theme = request.COOKIES.get("vector_theme", "light")
    if theme not in ("light", "dark"):
        theme = "light"
    return {
        "PANEL_THEME": theme,
        "PANEL_LANGUAGES": LANGUAGES,
        "CURRENT_LANGUAGE": get_language() or "uz",
        "DEBUG": settings.DEBUG,
    }
