"""Kontent tarjimalari uchun yengil mexanizm.

Har bir modelda `i18n` (JSON) maydoni bo'ladi:
    {"ru": {"title": "...", "description": "..."}, "en": {...}, "uz-cyrl": {...}}
Asosiy (uz) qiymat oddiy maydonda turadi. Tarjima topilmasa — asosiysi qaytadi.
"""
from django.db import models
from django.utils.translation import get_language

# Loyihada qo'llab-quvvatlanadigan tillar
LANGUAGES = (
    ("uz", "O'zbekcha"),
    ("uz-cyrl", "Ўзбекча"),
    ("ru", "Русский"),
    ("en", "English"),
)
LANGUAGE_CODES = [code for code, _ in LANGUAGES]
DEFAULT_LANGUAGE = "uz"


class TranslatableMixin(models.Model):
    """Tarjima qilinadigan matnli maydonlarga ega modellar uchun."""

    #: Qaysi maydonlar tarjima qilinadi — voris klassda belgilanadi
    translatable_fields = ()

    i18n = models.JSONField("Tarjimalar", default=dict, blank=True)

    class Meta:
        abstract = True

    def t(self, field, language=None):
        """Joriy (yoki ko'rsatilgan) tildagi qiymatni qaytaradi."""
        base = getattr(self, field, "") or ""
        lang = (language or get_language() or DEFAULT_LANGUAGE).lower()
        if lang.startswith(DEFAULT_LANGUAGE) and lang != "uz-cyrl":
            return base
        data = self.i18n or {}
        value = (data.get(lang) or {}).get(field)
        if not value and "-" in lang:
            value = (data.get(lang.split("-")[0]) or {}).get(field)
        return value or base

    def set_translation(self, language, field, value):
        data = dict(self.i18n or {})
        bucket = dict(data.get(language) or {})
        if value:
            bucket[field] = value
        else:
            bucket.pop(field, None)
        if bucket:
            data[language] = bucket
        else:
            data.pop(language, None)
        self.i18n = data

    def translations_for(self, language):
        return (self.i18n or {}).get(language, {})
