"""Telegram webhookni o'rnatadi.

Ishlatish:  python manage.py setwebhook https://sizning-domeningiz.uz
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Telegram webhookni o'rnatadi"

    def add_arguments(self, parser):
        parser.add_argument("base_url", help="Masalan: https://vector.uz")

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError(".env faylida TELEGRAM_BOT_TOKEN yo'q.")
        secret = settings.SECRET_KEY[:24]
        url = options["base_url"].rstrip("/") + f"/api/auth/telegram/webhook/{secret}/"
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": url, "allowed_updates": ["message"]},
            timeout=10,
        ).json()
        if resp.get("ok"):
            self.stdout.write(self.style.SUCCESS(f"Webhook o'rnatildi: {url}"))
        else:
            raise CommandError(f"Xato: {resp}")
