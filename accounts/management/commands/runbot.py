"""Telegram botni long-polling rejimida ishga tushiradi.

Ishlatish:  python manage.py runbot
"""
import logging
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bot.handlers import handle_update

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Telegram tasdiqlash botini ishga tushiradi (long polling)"

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError(".env faylida TELEGRAM_BOT_TOKEN ko'rsatilmagan.")

        base = f"https://api.telegram.org/bot{token}"
        me = requests.get(f"{base}/getMe", timeout=10).json()
        if not me.get("ok"):
            raise CommandError(f"Bot tokeni noto'g'ri: {me}")
        username = me["result"]["username"]
        self.stdout.write(self.style.SUCCESS(f"Bot ishga tushdi: @{username}"))
        if username != (settings.TELEGRAM_BOT_USERNAME or "").lstrip("@"):
            self.stdout.write(self.style.WARNING(
                f"Diqqat: .env dagi TELEGRAM_BOT_USERNAME '{settings.TELEGRAM_BOT_USERNAME}' "
                f"botning haqiqiy username'i '{username}' bilan mos emas."
            ))

        # Webhook o'rnatilgan bo'lsa, polling ishlamaydi
        requests.get(f"{base}/deleteWebhook", timeout=10)

        offset = None
        while True:
            try:
                resp = requests.get(
                    f"{base}/getUpdates",
                    params={"timeout": 30, "offset": offset,
                            "allowed_updates": '["message"]'},
                    timeout=40,
                ).json()
            except requests.RequestException as exc:
                logger.warning("Tarmoq xatosi: %s", exc)
                time.sleep(3)
                continue

            if not resp.get("ok"):
                logger.error("getUpdates xatosi: %s", resp)
                time.sleep(3)
                continue

            for update in resp.get("result", []):
                offset = update["update_id"] + 1
                handle_update(update)
