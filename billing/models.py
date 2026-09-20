"""Premium tariflar, obunalar va to'lovlar (Payme / Click)."""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from core.i18n import TranslatableMixin
from core.models import TimeStampedModel


class Plan(TranslatableMixin, TimeStampedModel):
    """Premium tarif: START / PRO / VIP."""

    translatable_fields = ("name", "description", "features_text")

    PERIOD_MONTH = "month"
    PERIOD_YEAR = "year"
    PERIOD_CHOICES = [(PERIOD_MONTH, _("Oylik")), (PERIOD_YEAR, _("Yillik"))]

    name = models.CharField("Tarif nomi", max_length=60)
    code = models.SlugField("Kod", max_length=40, unique=True)
    description = models.CharField("Qisqa tavsif", max_length=200, blank=True)
    features_text = models.TextField(
        "Imkoniyatlar", blank=True,
        help_text="Har bir imkoniyat alohida qatorda yozilsin",
    )

    price = models.DecimalField("Narxi (so'm)", max_digits=12, decimal_places=2, default=0)
    old_price = models.DecimalField("Eski narxi", max_digits=12, decimal_places=2, default=0)
    period = models.CharField("Muddat turi", max_length=8, choices=PERIOD_CHOICES, default=PERIOD_MONTH)
    duration_days = models.PositiveIntegerField("Amal qilish muddati (kun)", default=30)

    is_active = models.BooleanField("Faol", default=True)
    is_popular = models.BooleanField("Eng ommabop (ajratib ko'rsatilsin)", default=False)
    color = models.CharField("Rang", max_length=9, default="#1F6FEB")
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Premium tarif"
        verbose_name_plural = "Premium tariflar"
        ordering = ("order", "price")

    def __str__(self):
        return f"{self.name} — {self.price:,.0f} so'm".replace(",", " ")

    @property
    def features(self):
        return [line.strip() for line in (self.features_text or "").splitlines() if line.strip()]

    def features_for(self, language):
        text = self.t("features_text", language)
        return [line.strip() for line in (text or "").splitlines() if line.strip()]


class PromoCode(TimeStampedModel):
    """Talabalarga tarqatiladigan promo kod — Premium xaridida chegirma beradi."""

    code = models.CharField("Kod", max_length=40, unique=True, db_index=True)
    discount_percent = models.PositiveSmallIntegerField("Chegirma (%)", default=10)
    is_active = models.BooleanField("Faol", default=True)
    max_uses = models.PositiveIntegerField("Maksimal ishlatilish soni (0 — cheklanmagan)", default=0)
    used_count = models.PositiveIntegerField("Ishlatilgan soni", default=0)
    note = models.CharField("Izoh", max_length=200, blank=True)

    class Meta:
        verbose_name = "Promo kod"
        verbose_name_plural = "Promo kodlar"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.code} (-{self.discount_percent}%)"

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    @property
    def is_usable(self):
        if not self.is_active:
            return False
        if self.max_uses and self.used_count >= self.max_uses:
            return False
        return True

    def apply_to(self, amount):
        """Berilgan summaga chegirmani qo'llab, yangi summani qaytaradi."""
        from decimal import Decimal
        discount = Decimal(amount) * Decimal(self.discount_percent) / Decimal(100)
        return max(Decimal(0), Decimal(amount) - discount)

    def mark_used(self):
        self.used_count += 1
        self.save(update_fields=["used_count"])


class Subscription(TimeStampedModel):
    """Foydalanuvchining premium obunasi."""

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, _("To'lov kutilmoqda")),
        (STATUS_ACTIVE, _("Faol")),
        (STATUS_EXPIRED, _("Muddati tugagan")),
        (STATUS_CANCELLED, _("Bekor qilingan")),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="subscriptions", verbose_name="Foydalanuvchi")
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True,
                             related_name="subscriptions", verbose_name="Tarif")
    plan_name = models.CharField("Tarif nomi", max_length=60, blank=True)
    amount = models.DecimalField("Summa", max_digits=12, decimal_places=2, default=0)

    status = models.CharField("Holat", max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    starts_at = models.DateTimeField("Boshlanish", null=True, blank=True)
    ends_at = models.DateTimeField("Tugash", null=True, blank=True)
    is_auto_renew = models.BooleanField("Avtomatik yangilash", default=False)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="granted_subscriptions", verbose_name="Qo'lda bergan admin")
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="subscriptions", verbose_name="Promo kod")

    class Meta:
        verbose_name = "Obuna"
        verbose_name_plural = "Obunalar"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.full_name} — {self.plan_name or '—'}"

    def save(self, *args, **kwargs):
        if self.plan and not self.plan_name:
            self.plan_name = self.plan.name
        if self.plan and not self.amount:
            self.amount = self.plan.price
        super().save(*args, **kwargs)

    @property
    def is_live(self):
        return self.status == self.STATUS_ACTIVE and (not self.ends_at or self.ends_at > timezone.now())

    @property
    def days_left(self):
        if not self.ends_at:
            return 0
        delta = self.ends_at - timezone.now()
        return max(0, delta.days)

    def activate(self, days=None):
        """Obunani faollashtiradi."""
        days = days or (self.plan.duration_days if self.plan else 30)
        now = timezone.now()
        # Amaldagi obuna bo'lsa — muddatini uzaytiramiz
        base = self.ends_at if (self.ends_at and self.ends_at > now) else now
        self.starts_at = self.starts_at or now
        self.ends_at = base + timedelta(days=days)
        self.status = self.STATUS_ACTIVE
        self.save(update_fields=["starts_at", "ends_at", "status"])
        return self

    def cancel(self):
        self.status = self.STATUS_CANCELLED
        self.save(update_fields=["status"])


class Payment(TimeStampedModel):
    """To'lov tranzaksiyasi (Payme / Click / qo'lda)."""

    PROVIDER_PAYME = "payme"
    PROVIDER_CLICK = "click"
    PROVIDER_MANUAL = "manual"
    PROVIDER_CHOICES = [
        (PROVIDER_PAYME, "Payme"),
        (PROVIDER_CLICK, "Click"),
        (PROVIDER_MANUAL, _("Qo'lda")),
    ]

    STATE_CREATED = "created"        # yaratildi, to'lov kutilmoqda
    STATE_HOLD = "hold"              # pul ushlab turibdi (payme: 1)
    STATE_PAID = "paid"              # to'landi (payme: 2)
    STATE_CANCELLED = "cancelled"    # bekor qilindi (payme: -1/-2)
    STATE_CHOICES = [
        (STATE_CREATED, _("Yaratilgan")),
        (STATE_HOLD, _("Ushlab turilgan")),
        (STATE_PAID, _("To'langan")),
        (STATE_CANCELLED, _("Bekor qilingan")),
    ]

    TARGET_SUBSCRIPTION = "subscription"
    TARGET_ORDER = "order"
    TARGET_COURSE = "course"
    TARGET_CHOICES = [
        (TARGET_SUBSCRIPTION, _("Premium obuna")),
        (TARGET_ORDER, _("Do'kon buyurtmasi")),
        (TARGET_COURSE, _("Kurs")),
    ]

    # Ichki identifikator — to'lov tizimlariga account sifatida uzatiladi
    reference = models.CharField("Ichki raqam", max_length=32, unique=True, blank=True, db_index=True)
    provider = models.CharField("To'lov tizimi", max_length=10, choices=PROVIDER_CHOICES, default=PROVIDER_PAYME)
    target_type = models.CharField("Nima uchun", max_length=16, choices=TARGET_CHOICES,
                                   default=TARGET_SUBSCRIPTION)
    target_id = models.PositiveIntegerField("Obyekt ID", null=True, blank=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                             related_name="payments", verbose_name="Foydalanuvchi")
    amount = models.DecimalField("Summa (so'm)", max_digits=14, decimal_places=2, default=0)
    state = models.CharField("Holat", max_length=12, choices=STATE_CHOICES, default=STATE_CREATED)

    # Tashqi tizim ma'lumotlari
    external_id = models.CharField("Tashqi tranzaksiya ID", max_length=100, blank=True, db_index=True)
    perform_time = models.BigIntegerField("To'langan vaqt (ms)", default=0)
    cancel_time = models.BigIntegerField("Bekor qilingan vaqt (ms)", default=0)
    create_time = models.BigIntegerField("Yaratilgan vaqt (ms)", default=0)
    cancel_reason = models.IntegerField("Bekor qilish sababi", null=True, blank=True)
    raw = models.JSONField("Xom javob", default=dict, blank=True)

    class Meta:
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["provider", "external_id"])]

    def __str__(self):
        return f"{self.get_provider_display()} — {self.amount:,.0f}".replace(",", " ")

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = get_random_string(16, "abcdefghijklmnopqrstuvwxyz0123456789")
        super().save(*args, **kwargs)

    # --- Holat o'zgarishlari ---
    def mark_paid(self):
        """To'lov muvaffaqiyatli — tegishli obyektni faollashtiradi."""
        if self.state == self.STATE_PAID:
            return self
        self.state = self.STATE_PAID
        self.perform_time = int(timezone.now().timestamp() * 1000)
        self.save(update_fields=["state", "perform_time"])
        self._apply()
        return self

    def mark_cancelled(self, reason=None):
        self.state = self.STATE_CANCELLED
        self.cancel_time = int(timezone.now().timestamp() * 1000)
        self.cancel_reason = reason
        self.save(update_fields=["state", "cancel_time", "cancel_reason"])
        self._revert()
        return self

    def _apply(self):
        """To'lovdan keyin obyektni faollashtirish."""
        if self.target_type == self.TARGET_SUBSCRIPTION:
            sub = Subscription.objects.filter(pk=self.target_id).first()
            if sub:
                sub.activate()
        elif self.target_type == self.TARGET_ORDER:
            from shop.models import Order
            order = Order.objects.filter(pk=self.target_id).first()
            if order:
                order.mark_paid()
        elif self.target_type == self.TARGET_COURSE:
            from courses.models import Course, Enrollment
            course = Course.objects.filter(pk=self.target_id).first()
            if course and self.user:
                Enrollment.objects.update_or_create(
                    user=self.user, course=course, defaults={"is_paid": True}
                )

    def _revert(self):
        """To'lov bekor qilinganda ta'sirini qaytarish."""
        if self.target_type == self.TARGET_SUBSCRIPTION:
            sub = Subscription.objects.filter(pk=self.target_id).first()
            if sub and sub.status == Subscription.STATUS_ACTIVE:
                sub.cancel()
        elif self.target_type == self.TARGET_ORDER:
            from shop.models import Order
            order = Order.objects.filter(pk=self.target_id).first()
            if order:
                order.status = Order.STATUS_CANCELLED
                order.save(update_fields=["status"])
