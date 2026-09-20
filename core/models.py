"""Umumiy kontent modellari: bannerlar, bildirishnomalar, sozlamalar, jurnal."""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .i18n import TranslatableMixin


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)
    updated_at = models.DateTimeField("Yangilangan", auto_now=True)

    class Meta:
        abstract = True


class Banner(TranslatableMixin, TimeStampedModel):
    """Bosh sahifadagi reklama banneri."""

    translatable_fields = ("title", "subtitle", "button_text")

    PLACEMENT_HOME = "home"
    PLACEMENT_COURSES = "courses"
    PLACEMENT_SHOP = "shop"
    PLACEMENT_CHOICES = [
        (PLACEMENT_HOME, _("Bosh sahifa")),
        (PLACEMENT_COURSES, _("Kurslar sahifasi")),
        (PLACEMENT_SHOP, _("Do'kon sahifasi")),
    ]

    title = models.CharField("Sarlavha", max_length=140)
    subtitle = models.TextField("Matn", blank=True)
    image = models.ImageField("Banner rasmi", upload_to="banners/", blank=True)
    button_text = models.CharField("Tugma matni", max_length=60, blank=True)
    button_url = models.CharField("Tugma havolasi", max_length=300, blank=True)
    placement = models.CharField("Joylashuv", max_length=16, choices=PLACEMENT_CHOICES, default=PLACEMENT_HOME)
    starts_at = models.DateTimeField("Boshlanish sanasi", null=True, blank=True)
    ends_at = models.DateTimeField("Tugash sanasi", null=True, blank=True)
    is_active = models.BooleanField("Aktiv", default=True)
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Banner"
        verbose_name_plural = "Bannerlar"
        ordering = ("order", "-created_at")

    def __str__(self):
        return self.title

    @property
    def is_live(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True


class Notification(TranslatableMixin, TimeStampedModel):
    """Foydalanuvchilarga yuboriladigan xabar."""

    translatable_fields = ("title", "body")

    AUDIENCE_ALL = "all"
    AUDIENCE_PREMIUM = "premium"
    AUDIENCE_FREE = "free"
    AUDIENCE_STUDENTS = "students"
    AUDIENCE_TEACHERS = "teachers"
    AUDIENCE_COURSE = "course"
    AUDIENCE_CHOICES = [
        (AUDIENCE_ALL, _("Barcha foydalanuvchilar")),
        (AUDIENCE_PREMIUM, _("Faqat premium")),
        (AUDIENCE_FREE, _("Faqat oddiy")),
        (AUDIENCE_STUDENTS, _("O'quvchilar")),
        (AUDIENCE_TEACHERS, _("O'qituvchilar")),
        (AUDIENCE_COURSE, _("Muayyan kurs o'quvchilari")),
    ]

    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_CHOICES = [(STATUS_DRAFT, _("Qoralama")), (STATUS_SENT, _("Yuborilgan"))]

    title = models.CharField("Sarlavha", max_length=140)
    body = models.TextField("Matn")
    image = models.ImageField("Rasm", upload_to="notifications/", blank=True)
    audience = models.CharField("Kimga", max_length=16, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    course = models.ForeignKey(
        "courses.Course", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="notifications", verbose_name="Kurs",
    )
    send_push = models.BooleanField("Push yuborilsin", default=True)
    send_telegram = models.BooleanField("Telegramga ham yuborilsin", default=False)
    status = models.CharField("Holat", max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    sent_at = models.DateTimeField("Yuborilgan vaqt", null=True, blank=True)
    recipients_count = models.PositiveIntegerField("Qabul qiluvchilar", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_notifications", verbose_name="Kim yaratdi",
    )

    class Meta:
        verbose_name = "Bildirishnoma"
        verbose_name_plural = "Bildirishnomalar"
        ordering = ("-created_at",)

    def __str__(self):
        return self.title

    def audience_queryset(self):
        """Kimlarga yuborilishini aniqlaydi."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        qs = User.objects.filter(is_active=True, is_phone_verified=True)
        if self.audience == self.AUDIENCE_PREMIUM:
            return qs.filter(subscriptions__status="active").distinct()
        if self.audience == self.AUDIENCE_FREE:
            return qs.exclude(subscriptions__status="active").distinct()
        if self.audience == self.AUDIENCE_STUDENTS:
            return qs.filter(role=User.ROLE_STUDENT)
        if self.audience == self.AUDIENCE_TEACHERS:
            return qs.filter(role=User.ROLE_TEACHER)
        if self.audience == self.AUDIENCE_COURSE and self.course_id:
            return qs.filter(enrollments__course_id=self.course_id).distinct()
        return qs


class NotificationDelivery(models.Model):
    """Bildirishnomaning bitta foydalanuvchiga yetkazilishi."""

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="deliveries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    is_read = models.BooleanField("O'qilgan", default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Yetkazilgan bildirishnoma"
        verbose_name_plural = "Yetkazilgan bildirishnomalar"
        unique_together = ("notification", "user")
        ordering = ("-created_at",)

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class SiteSetting(models.Model):
    """Sayt sozlamalari — bitta yozuv (singleton)."""

    site_name = models.CharField("Sayt nomi", max_length=80, default="VECTOR")
    tagline = models.CharField("Shior", max_length=160, blank=True,
                               default="O'zbekistondagi 1-raqamli onlayn ta'lim platformasi")
    support_phone = models.CharField("Qo'llab-quvvatlash raqami", max_length=20, blank=True)
    support_telegram = models.CharField("Telegram", max_length=80, blank=True)
    instagram = models.CharField("Instagram", max_length=120, blank=True)
    youtube = models.CharField("YouTube", max_length=120, blank=True)
    android_url = models.CharField("Google Play havolasi", max_length=200, blank=True)
    ios_url = models.CharField("App Store havolasi", max_length=200, blank=True)
    terms_url = models.CharField("Foydalanish shartnomasi havolasi", max_length=200, blank=True)
    maintenance_mode = models.BooleanField("Texnik ish rejimi", default=False)
    default_language = models.CharField("Standart til", max_length=10, default="uz")

    class Meta:
        verbose_name = "Sayt sozlamasi"
        verbose_name_plural = "Sayt sozlamalari"

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1  # doim bitta yozuv
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ActivityLog(models.Model):
    """Admin panelda bajarilgan amallar jurnali."""

    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_CHOICES = [
        (ACTION_CREATE, _("Qo'shildi")),
        (ACTION_UPDATE, _("O'zgartirildi")),
        (ACTION_DELETE, _("O'chirildi")),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                             related_name="activity_logs")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=60)
    object_id = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Amal jurnali"
        verbose_name_plural = "Amallar jurnali"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_action_display()} — {self.model_name}"

    @classmethod
    def write(cls, user, action, obj, description=""):
        try:
            cls.objects.create(
                user=user if getattr(user, "is_authenticated", False) else None,
                action=action,
                model_name=obj.__class__.__name__,
                object_id=str(getattr(obj, "pk", "") or ""),
                description=description or str(obj)[:250],
            )
        except Exception:  # jurnal hech qachon asosiy amalni to'xtatmasin
            pass


class DailyStat(models.Model):
    """Kunlik statistika (grafiklar tez chizilishi uchun)."""

    date = models.DateField("Sana", unique=True)
    new_users = models.PositiveIntegerField("Yangi foydalanuvchilar", default=0)
    active_users = models.PositiveIntegerField("Faol foydalanuvchilar", default=0)
    enrollments = models.PositiveIntegerField("Kursga yozilishlar", default=0)
    orders = models.PositiveIntegerField("Buyurtmalar", default=0)
    revenue = models.DecimalField("Daromad", max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Kunlik statistika"
        verbose_name_plural = "Kunlik statistika"
        ordering = ("-date",)

    def __str__(self):
        return str(self.date)
