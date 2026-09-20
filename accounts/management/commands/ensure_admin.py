"""ADMIN_PHONE / ADMIN_PASSWORD environment o'zgaruvchilari orqali
birinchi admin (superuser) akkauntini avtomatik yaratadi."""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "ADMIN_PHONE/ADMIN_PASSWORD env orqali superuser borligini ta'minlaydi"

    def handle(self, *args, **options):
        phone = os.getenv("ADMIN_PHONE")
        password = os.getenv("ADMIN_PASSWORD")

        if not phone or not password:
            self.stdout.write("ADMIN_PHONE yoki ADMIN_PASSWORD o'rnatilmagan — o'tkazib yuborildi.")
            return

        User = get_user_model()

        if User.objects.filter(phone=phone).exists():
            self.stdout.write(f"{phone} allaqachon mavjud — o'zgartirilmadi.")
            return

        User.objects.create_superuser(phone=phone, password=password, full_name="Admin")
        self.stdout.write(self.style.SUCCESS(f"Superuser yaratildi: {phone}"))
