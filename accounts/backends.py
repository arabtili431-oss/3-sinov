"""Telefon raqam bo'yicha autentifikatsiya backend'i.

Foydalanuvchi raqamni qanday yozishidan qat'i nazar (901234567,
90 123 45 67, 998901234567, +998901234567) tizim uni topa oladi.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from .utils import normalize_phone

User = get_user_model()


class PhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        raw = username or kwargs.get("phone") or kwargs.get(User.USERNAME_FIELD)
        if not raw or not password:
            return None

        phone = normalize_phone(raw)
        user = None
        if phone:
            user = User.objects.filter(phone=phone).first()
        if user is None:
            # Raqam formatiga tushmasa ham aynan mos keladiganini qidiramiz
            user = User.objects.filter(phone=str(raw).strip()).first()
        if user is None:
            # Vaqt hujumidan himoya: parolni baribir hisoblaymiz
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
