"""Kurslar, modullar, darslar va o'quvchi progressi."""
from django.conf import settings
from django.db import models
from django.db.models import Avg, Count
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.i18n import TranslatableMixin
from core.models import TimeStampedModel


class Category(TranslatableMixin, TimeStampedModel):
    """Kurs kategoriyasi: Dasturlash, Dizayn, Kiber xavfsizlik va h.k."""

    translatable_fields = ("name", "description")

    name = models.CharField("Nomi", max_length=90)
    slug = models.SlugField("Slug", max_length=110, unique=True, blank=True)
    description = models.TextField("Tavsif", blank=True)
    icon = models.CharField("Ikonka (emoji yoki nom)", max_length=40, blank=True)
    color = models.CharField("Rang", max_length=9, default="#1F6FEB")
    image = models.ImageField("Rasm", upload_to="categories/", blank=True)
    order = models.PositiveIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Aktiv", default=True)

    class Meta:
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        ordering = ("order", "name")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "kategoriya"
            slug, i = base, 2
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Course(TranslatableMixin, TimeStampedModel):
    """Kurs — platformaning asosiy birligi."""

    translatable_fields = ("title", "short_description", "description")

    ACCESS_FREE = "free"
    ACCESS_PREMIUM = "premium"
    ACCESS_PAID = "paid"
    ACCESS_CHOICES = [
        (ACCESS_FREE, _("Bepul")),
        (ACCESS_PREMIUM, _("Premium obuna bilan")),
        (ACCESS_PAID, _("Alohida sotib olinadi")),
    ]

    LEVEL_BEGINNER = "beginner"
    LEVEL_MIDDLE = "middle"
    LEVEL_ADVANCED = "advanced"
    LEVEL_CHOICES = [
        (LEVEL_BEGINNER, _("Boshlang'ich")),
        (LEVEL_MIDDLE, _("O'rta")),
        (LEVEL_ADVANCED, _("Yuqori")),
    ]

    title = models.CharField("Kurs nomi", max_length=160)
    slug = models.SlugField("Slug", max_length=180, unique=True, blank=True)
    short_description = models.CharField("Qisqa tavsif", max_length=250, blank=True)
    description = models.TextField("To'liq tavsif", blank=True)
    cover = models.ImageField("Kurs rasmi", upload_to="courses/", blank=True)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="courses", verbose_name="Kategoriya")
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="teaching_courses", verbose_name="O'qituvchi",
                                limit_choices_to={"role__in": ["teacher", "admin"]})
    teacher_name = models.CharField("O'qituvchi ismi (matn)", max_length=120, blank=True,
                                    help_text="Agar o'qituvchi tizimda ro'yxatdan o'tmagan bo'lsa")

    access = models.CharField("Kirish turi", max_length=10, choices=ACCESS_CHOICES, default=ACCESS_PREMIUM)
    price = models.DecimalField("Narxi (so'm)", max_digits=12, decimal_places=2, default=0)
    old_price = models.DecimalField("Eski narxi", max_digits=12, decimal_places=2, default=0)
    level = models.CharField("Daraja", max_length=12, choices=LEVEL_CHOICES, default=LEVEL_BEGINNER)

    is_active = models.BooleanField("Faol", default=True)
    is_featured = models.BooleanField("Bosh sahifada ko'rsatilsin", default=False)
    order = models.PositiveIntegerField("Tartib", default=0)
    published_at = models.DateTimeField("E'lon qilingan", null=True, blank=True)

    class Meta:
        verbose_name = "Kurs"
        verbose_name_plural = "Kurslar"
        ordering = ("order", "-created_at")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "kurs"
            slug, i = base, 2
            while Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        if self.is_active and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    # --- Hisob-kitoblar ---
    @property
    def lessons_count(self):
        return Lesson.objects.filter(module__course=self).count()

    @property
    def students_count(self):
        return self.enrollments.count()

    @property
    def total_duration(self):
        """Barcha darslar davomiyligi (soniya)."""
        total = Lesson.objects.filter(module__course=self).aggregate(s=models.Sum("duration"))["s"]
        return total or 0

    @property
    def teacher_display(self):
        if self.teacher:
            return self.teacher.full_name
        return self.teacher_name or "—"

    @property
    def average_progress(self):
        value = self.enrollments.aggregate(p=Avg("progress"))["p"]
        return round(value or 0)

    def is_available_for(self, user):
        """Foydalanuvchi kursni ocha oladimi?"""
        if self.access == self.ACCESS_FREE:
            return True
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or getattr(user, "is_admin_role", False):
            return True
        if self.access == self.ACCESS_PREMIUM:
            return user.has_active_subscription
        return self.enrollments.filter(user=user, is_paid=True).exists()


class Module(TranslatableMixin, models.Model):
    """Kurs ichidagi bo'lim (modul)."""

    translatable_fields = ("title", "description")

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules", verbose_name="Kurs")
    title = models.CharField("Modul nomi", max_length=160)
    description = models.TextField("Tavsif", blank=True)
    order = models.PositiveIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Modul"
        verbose_name_plural = "Modullar"
        ordering = ("order", "id")

    def __str__(self):
        return f"{self.course.title} — {self.title}"


class Lesson(TranslatableMixin, TimeStampedModel):
    """Dars: video + matn + fayllar."""

    translatable_fields = ("title", "description", "text")

    VIDEO_TELEGRAM = "telegram"
    VIDEO_URL = "url"
    VIDEO_NONE = "none"
    VIDEO_SOURCE_CHOICES = [
        (VIDEO_TELEGRAM, _("Telegram (yopiq kanal)")),
        (VIDEO_URL, _("Tashqi havola")),
        (VIDEO_NONE, _("Videosiz")),
    ]

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="lessons", verbose_name="Modul")
    title = models.CharField("Dars nomi", max_length=160)
    description = models.CharField("Qisqa tavsif", max_length=250, blank=True)
    text = models.TextField("Dars matni", blank=True)

    video_source = models.CharField("Video manbasi", max_length=10,
                                    choices=VIDEO_SOURCE_CHOICES, default=VIDEO_NONE)
    video_url = models.CharField("Video havolasi", max_length=400, blank=True,
                                 help_text="YouTube, Vimeo yoki to'g'ridan-to'g'ri MP4")
    telegram_file_id = models.CharField("Telegram file_id", max_length=200, blank=True)
    telegram_message_id = models.BigIntegerField("Telegram xabar ID", null=True, blank=True)
    video_size = models.BigIntegerField("Video hajmi (bayt)", default=0)
    thumbnail = models.ImageField("Video muqovasi", upload_to="lessons/", blank=True)
    duration = models.PositiveIntegerField("Davomiyligi (soniya)", default=0)

    is_free = models.BooleanField("Bepul (demo dars)", default=False)
    is_active = models.BooleanField("Faol", default=True)
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Dars"
        verbose_name_plural = "Darslar"
        ordering = ("order", "id")

    def __str__(self):
        return self.title

    @property
    def course(self):
        return self.module.course

    @property
    def duration_display(self):
        m, s = divmod(self.duration or 0, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    @property
    def has_video(self):
        return bool(self.telegram_file_id or self.video_url)

    def is_locked_for(self, user):
        """Dars foydalanuvchi uchun qulflanganmi?"""
        if self.is_free:
            return False
        return not self.module.course.is_available_for(user)


class LessonAttachment(models.Model):
    """Darsga biriktirilgan fayl (PDF, arxiv va h.k.)."""

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="attachments")
    title = models.CharField("Fayl nomi", max_length=160)
    file = models.FileField("Fayl", upload_to="attachments/", blank=True)
    telegram_file_id = models.CharField("Telegram file_id", max_length=200, blank=True)
    size = models.BigIntegerField("Hajmi (bayt)", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Dars fayli"
        verbose_name_plural = "Dars fayllari"
        ordering = ("id",)

    def __str__(self):
        return self.title


class Enrollment(models.Model):
    """Foydalanuvchining kursga yozilishi."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    progress = models.PositiveSmallIntegerField("Progress (%)", default=0)
    is_paid = models.BooleanField("To'langan", default=False)
    is_completed = models.BooleanField("Tugatilgan", default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_opened_at = models.DateTimeField("Oxirgi ochilgan", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Kursga yozilish"
        verbose_name_plural = "Kursga yozilishlar"
        unique_together = ("user", "course")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.full_name} — {self.course.title}"

    def recalculate(self):
        """Tugatilgan darslar asosida progressni qayta hisoblaydi."""
        total = Lesson.objects.filter(module__course=self.course, is_active=True).count()
        if not total:
            self.progress = 0
        else:
            done = LessonProgress.objects.filter(
                user=self.user, lesson__module__course=self.course, is_completed=True
            ).count()
            self.progress = min(100, round(done * 100 / total))
        self.is_completed = self.progress >= 100
        if self.is_completed and not self.completed_at:
            self.completed_at = timezone.now()
        self.save(update_fields=["progress", "is_completed", "completed_at"])
        return self.progress


class LessonProgress(models.Model):
    """Bitta darsning ko'rilganlik holati."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="progress")
    is_completed = models.BooleanField("Tugatilgan", default=False)
    seconds_watched = models.PositiveIntegerField("Ko'rilgan vaqt (soniya)", default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dars progressi"
        verbose_name_plural = "Dars progresslari"
        unique_together = ("user", "lesson")

    def __str__(self):
        return f"{self.user.full_name} — {self.lesson.title}"


class LessonQuiz(models.Model):
    """Darsga tegishli test: to'g'ri javob foiziga qarab Coin beriladi."""

    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name="quiz")
    coin_reward = models.PositiveIntegerField(
        "Maksimal Coin mukofoti", default=10,
        help_text="Test 100% to'g'ri yechilsa shuncha Coin beriladi; qisman yechilsa ulushi bo'yicha.",
    )
    pass_percent = models.PositiveSmallIntegerField("O'tish balli (%)", default=60)
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Dars testi"
        verbose_name_plural = "Dars testlari"

    def __str__(self):
        return f"Test: {self.lesson.title}"

    @property
    def questions_count(self):
        return self.questions.count()


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(LessonQuiz, on_delete=models.CASCADE, related_name="questions")
    text = models.CharField("Savol matni", max_length=300)
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Test savoli"
        verbose_name_plural = "Test savollari"
        ordering = ("order", "id")

    def __str__(self):
        return self.text


class QuizChoice(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField("Javob varianti", max_length=200)
    is_correct = models.BooleanField("To'g'ri javob", default=False)
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Javob varianti"
        verbose_name_plural = "Javob variantlari"
        ordering = ("order", "id")

    def __str__(self):
        return self.text


class QuizAttempt(models.Model):
    """Foydalanuvchining testni bir marta yechishi — Coin shu asosida beriladi."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quiz_attempts")
    quiz = models.ForeignKey(LessonQuiz, on_delete=models.CASCADE, related_name="attempts")
    score_percent = models.PositiveSmallIntegerField("Natija (%)", default=0)
    correct_count = models.PositiveSmallIntegerField("To'g'ri javoblar soni", default=0)
    total_count = models.PositiveSmallIntegerField("Jami savollar", default=0)
    coins_earned = models.PositiveIntegerField("Berilgan Coin", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Test urinishi"
        verbose_name_plural = "Test urinishlari"
        unique_together = ("user", "quiz")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.full_name} — {self.quiz.lesson.title} ({self.score_percent}%)"


class Certificate(models.Model):
    """Kurs yakunidagi sertifikat."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certificates")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="certificates")
    code = models.CharField("Sertifikat raqami", max_length=32, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sertifikat"
        verbose_name_plural = "Sertifikatlar"
        unique_together = ("user", "course")
        ordering = ("-issued_at",)

    def __str__(self):
        return self.code
