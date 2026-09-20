"""Foydalanuvchi va Telegram tasdiqlash modellari."""
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .utils import generate_code, normalize_phone


class UserManager(BaseUserManager):
    """Telefon raqam asosidagi foydalanuvchi menejeri."""

    use_in_migrations = True

    def _create_user(self, phone, password, **extra):
        phone = normalize_phone(phone)
        if not phone:
            raise ValueError("Telefon raqam noto'g'ri")
        user = self.model(phone=phone, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        extra.setdefault("is_active", False)  # Telegram tasdiqlangunicha faol emas
        return self._create_user(phone, password, **extra)

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        extra.setdefault("is_phone_verified", True)
        extra.setdefault("role", "admin")
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Superuser is_staff va is_superuser=True bo'lishi kerak")
        return self._create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Platforma foydalanuvchisi. Login uchun telefon raqam ishlatiladi."""

    phone = models.CharField("Telefon raqam", max_length=13, unique=True, db_index=True)
    full_name = models.CharField("Ism va familiya", max_length=120)
    region = models.CharField("Viloyat", max_length=80, blank=True)
    district = models.CharField("Shahar yoki tuman", max_length=80, blank=True)
    school = models.CharField("Maktab", max_length=80, blank=True)
    grade = models.CharField("Sinf", max_length=20, blank=True)
    birth_date = models.DateField("Tug'ilgan sana", null=True, blank=True)

    ROLE_STUDENT = "student"
    ROLE_TEACHER = "teacher"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = [
        (ROLE_STUDENT, _("O'quvchi")),
        (ROLE_TEACHER, _("O'qituvchi")),
        (ROLE_ADMIN, _("Administrator")),
    ]
    role = models.CharField(
        "Rol", max_length=16, choices=ROLE_CHOICES, default=ROLE_STUDENT, db_index=True
    )
    subject = models.CharField("Fan (o'qituvchilar uchun)", max_length=80, blank=True)

    telegram_id = models.BigIntegerField("Telegram ID", null=True, blank=True, unique=True)
    telegram_username = models.CharField("Telegram username", max_length=64, blank=True)

    avatar = models.ImageField("Rasm", upload_to="avatars/", blank=True)
    bio = models.TextField("Qisqacha ma'lumot", blank=True)

    # --- Coin (gamifikatsiya): darslar bo'yicha testlarni yechib topiladi,
    # do'kondagi (Sovg'a bo'limi) mahsulotlarga almashtiriladi.
    coins = models.PositiveIntegerField("Coin balansi", default=0)

    # --- Promo kod: ro'yxatdan o'tishda kiritiladi, birinchi Premium
    # xaridida bir marta chegirma sifatida qo'llaniladi.
    promo_code_used = models.CharField("Ishlatilgan promo kod", max_length=40, blank=True)
    promo_discount_applied = models.BooleanField("Promo chegirma ishlatilgan", default=False)

    is_phone_verified = models.BooleanField("Raqam tasdiqlangan", default=False)
    is_blocked = models.BooleanField("Bloklangan", default=False)
    blocked_reason = models.CharField("Bloklash sababi", max_length=200, blank=True)
    last_seen_at = models.DateTimeField("Oxirgi faollik", null=True, blank=True)
    is_active = models.BooleanField("Faol", default=False)
    is_staff = models.BooleanField("Xodim", default=False)
    date_joined = models.DateTimeField("Ro'yxatdan o'tgan sana", default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ("-date_joined",)

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    # --- Premium obuna ---
    @property
    def active_subscription(self):
        from django.utils import timezone
        return (
            self.subscriptions.filter(status="active")
            .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=timezone.now()))
            .order_by("-ends_at")
            .first()
        )

    @property
    def has_active_subscription(self):
        return self.active_subscription is not None

    @property
    def is_premium(self):
        return self.has_active_subscription

    @property
    def plan_name(self):
        sub = self.active_subscription
        return sub.plan_name if sub else ""

    @property
    def is_student(self):
        return self.role == self.ROLE_STUDENT

    @property
    def is_teacher(self):
        return self.role == self.ROLE_TEACHER

    @property
    def is_admin_role(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def first_name(self):
        return self.full_name.split(" ")[0] if self.full_name else ""

    def add_coins(self, amount):
        """Coin balansini oshiradi/kamaytiradi (amount manfiy ham bo'lishi mumkin)."""
        if not amount:
            return self.coins
        self.coins = max(0, self.coins + int(amount))
        self.save(update_fields=["coins"])
        return self.coins

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone) or self.phone
        super().save(*args, **kwargs)


class TelegramVerification(models.Model):
    """Telegram orqali yuboriladigan bir martalik kod (OTP) sessiyasi."""

    PURPOSE_REGISTER = "register"
    PURPOSE_LOGIN = "login"
    PURPOSE_RESET = "reset"
    PURPOSE_CHOICES = [
        (PURPOSE_REGISTER, "Ro'yxatdan o'tish"),
        (PURPOSE_LOGIN, "Kirish"),
        (PURPOSE_RESET, "Parolni tiklash"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verifications",
        null=True,
        blank=True,
    )
    phone = models.CharField("Telefon raqam", max_length=13, db_index=True)
    purpose = models.CharField("Maqsad", max_length=16, choices=PURPOSE_CHOICES, default=PURPOSE_REGISTER)

    # Botga deep-link orqali uzatiladigan token: https://t.me/<bot>?start=<start_token>
    start_token = models.CharField("Start token", max_length=48, unique=True, db_index=True)

    code_hash = models.CharField("Kod (hash)", max_length=128, blank=True)
    telegram_chat_id = models.BigIntegerField("Telegram chat ID", null=True, blank=True)

    code_sent_at = models.DateTimeField("Kod yuborilgan vaqt", null=True, blank=True)
    attempts = models.PositiveSmallIntegerField("Urinishlar", default=0)
    is_used = models.BooleanField("Ishlatilgan", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField("Amal qilish muddati")

    class Meta:
        verbose_name = "Telegram tasdiqlash"
        verbose_name_plural = "Telegram tasdiqlashlar"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.phone} / {self.get_purpose_display()}"

    # --- Holat ---
    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_code_sent(self) -> bool:
        return bool(self.code_hash and self.telegram_chat_id)

    @property
    def status(self) -> str:
        """Frontend uchun holat: waiting_start | code_sent | expired | used"""
        if self.is_used:
            return "used"
        if self.is_expired:
            return "expired"
        return "code_sent" if self.is_code_sent else "waiting_start"

    # --- Amallar ---
    @classmethod
    def start(cls, phone, purpose=PURPOSE_REGISTER, user=None):
        """Yangi tasdiqlash sessiyasini ochadi va eskilarini bekor qiladi."""
        cls.objects.filter(phone=phone, purpose=purpose, is_used=False).update(
            is_used=True
        )
        ttl = getattr(settings, "OTP_TTL_SECONDS", 300)
        return cls.objects.create(
            user=user,
            phone=phone,
            purpose=purpose,
            start_token=uuid.uuid4().hex,
            expires_at=timezone.now() + timedelta(seconds=ttl),
        )

    def issue_code(self, chat_id=None) -> str:
        """Yangi kod generatsiya qiladi, hashlab saqlaydi va ochiq matnini qaytaradi."""
        code = generate_code(5)
        self.code_hash = make_password(code)
        self.code_sent_at = timezone.now()
        self.attempts = 0
        ttl = getattr(settings, "OTP_TTL_SECONDS", 300)
        self.expires_at = timezone.now() + timedelta(seconds=ttl)
        if chat_id:
            self.telegram_chat_id = chat_id
        self.save(update_fields=[
            "code_hash", "code_sent_at", "attempts", "expires_at", "telegram_chat_id",
        ])
        return code

    def check_code(self, code: str) -> bool:
        """Kodni tekshiradi; urinishlar sonini oshiradi."""
        if not self.code_hash:
            return False
        self.attempts += 1
        self.save(update_fields=["attempts"])
        return check_password(str(code).strip(), self.code_hash)
