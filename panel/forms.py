"""Admin panel formalari."""
from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from billing.models import Plan, PromoCode, Subscription
from core.i18n import LANGUAGE_CODES, LANGUAGES
from core.models import Banner, Notification, SiteSetting
from courses.models import Category, Course, Lesson, LessonAttachment, LessonQuiz, Module
from shop.models import Order, Product, ProductCategory

User = get_user_model()

TEXT = {"class": "input"}
AREA = {"class": "textarea", "rows": 4}
SELECT = {"class": "select"}


class StyledFormMixin:
    """Barcha maydonlarga bir xil CSS klass beradi."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "select")
            elif isinstance(widget, forms.CheckboxInput):
                pass
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "textarea")
                widget.attrs.setdefault("rows", 4)
            elif isinstance(widget, forms.ClearableFileInput):
                widget.attrs.setdefault("class", "file")
            else:
                widget.attrs.setdefault("class", "input")


class TranslationMixin(StyledFormMixin):
    """`i18n` JSON maydonini til bo'yicha alohida inputlarga ajratadi.

    Model `translatable_fields` ni belgilagan bo'lsa, har bir til uchun
    `<field>_<lang>` ko'rinishidagi qo'shimcha maydonlar hosil bo'ladi.
    """

    extra_languages = [code for code, _label in LANGUAGES if code != "uz"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model = self._meta.model
        self.translatable = list(getattr(model, "translatable_fields", ()) or ())
        instance = getattr(self, "instance", None)

        for lang in self.extra_languages:
            for field_name in self.translatable:
                base_field = self.fields.get(field_name)
                if base_field is None:
                    continue
                key = f"{field_name}__{lang}"
                widget = forms.Textarea(attrs={"class": "textarea", "rows": 4}) \
                    if isinstance(base_field.widget, forms.Textarea) \
                    else forms.TextInput(attrs={"class": "input"})
                self.fields[key] = forms.CharField(
                    label=base_field.label, required=False, widget=widget,
                )
                if instance and instance.pk:
                    self.fields[key].initial = instance.translations_for(lang).get(field_name, "")

    def translation_fields(self, lang):
        """Shablon uchun: bitta tildagi maydonlar ro'yxati."""
        return [self[f"{name}__{lang}"] for name in self.translatable if f"{name}__{lang}" in self.fields]

    def save(self, commit=True):
        obj = super().save(commit=False)
        for lang in self.extra_languages:
            for field_name in self.translatable:
                key = f"{field_name}__{lang}"
                if key in self.cleaned_data:
                    obj.set_translation(lang, field_name, self.cleaned_data[key].strip())
        if commit:
            obj.save()
            self.save_m2m()
        return obj


# ------------------------------------------------------------------ Kurslar
class CategoryForm(TranslationMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "description", "icon", "color", "image", "order", "is_active")
        widgets = {"color": forms.TextInput(attrs={"type": "color", "class": "input"})}


class CourseForm(TranslationMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = (
            "title", "short_description", "description", "cover", "category",
            "teacher", "teacher_name", "access", "price", "old_price", "level",
            "is_active", "is_featured", "order",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "short_description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = User.objects.filter(
            role__in=[User.ROLE_TEACHER, User.ROLE_ADMIN]
        ).order_by("full_name")
        self.fields["teacher"].required = False
        self.fields["category"].required = False

    def clean(self):
        data = super().clean()
        if data.get("access") == Course.ACCESS_PAID and not data.get("price"):
            self.add_error("price", _("Sotiladigan kurs uchun narx kiritilishi shart."))
        return data


class ModuleForm(TranslationMixin, forms.ModelForm):
    class Meta:
        model = Module
        fields = ("title", "description", "order", "is_active")


class LessonForm(TranslationMixin, forms.ModelForm):
    video_file = forms.FileField(
        label=_("Video fayl (MP4)"), required=False,
        help_text=_("Fayl yopiq Telegram kanaliga yuklanadi, serverda saqlanmaydi."),
        widget=forms.ClearableFileInput(attrs={"accept": "video/*"}),
    )

    class Meta:
        model = Lesson
        fields = (
            "module", "title", "description", "text", "video_source", "video_url",
            "thumbnail", "duration", "is_free", "is_active", "order",
        )
        widgets = {
            "text": forms.Textarea(attrs={"rows": 8}),
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        if course is not None:
            self.fields["module"].queryset = course.modules.all()
        self.fields["duration"].help_text = _("Soniyalarda. Masalan, 12 daqiqa = 720")

    def clean(self):
        data = super().clean()
        source = data.get("video_source")
        if source == Lesson.VIDEO_URL and not data.get("video_url"):
            self.add_error("video_url", _("Video havolasini kiriting."))
        if source == Lesson.VIDEO_TELEGRAM and not data.get("video_file"):
            if not (self.instance.pk and self.instance.telegram_file_id):
                self.add_error("video_file", _("Video faylni tanlang."))
        return data


class LessonQuizSettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = LessonQuiz
        fields = ("coin_reward", "pass_percent", "is_active")


class LessonAttachmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = LessonAttachment
        fields = ("title", "file")


# ------------------------------------------------------------------ Do'kon
class ProductCategoryForm(TranslationMixin, forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ("name", "order", "is_active")


class ProductForm(TranslationMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "name", "description", "image", "category", "price", "old_price",
            "stock", "sku", "is_active", "is_featured", "order",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].required = False


class OrderStatusForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Order
        fields = ("status", "full_name", "phone", "address", "comment")
        widgets = {"address": forms.Textarea(attrs={"rows": 3}),
                   "comment": forms.Textarea(attrs={"rows": 3})}


# ------------------------------------------------------------------ Premium
class PlanForm(TranslationMixin, forms.ModelForm):
    class Meta:
        model = Plan
        fields = (
            "name", "code", "description", "features_text", "price", "old_price",
            "period", "duration_days", "color", "is_active", "is_popular", "order",
        )
        widgets = {
            "features_text": forms.Textarea(attrs={"rows": 7}),
            "color": forms.TextInput(attrs={"type": "color", "class": "input"}),
        }


class PromoCodeForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PromoCode
        fields = ("code", "discount_percent", "max_uses", "is_active", "note")

    def clean_code(self):
        code = (self.cleaned_data["code"] or "").strip().upper()
        qs = PromoCode.objects.filter(code=code).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("Bu kod allaqachon mavjud."))
        return code


class GrantSubscriptionForm(StyledFormMixin, forms.Form):
    """Adminning qo'lda premium berishi."""

    user = forms.ModelChoiceField(label=_("Foydalanuvchi"), queryset=User.objects.none())
    plan = forms.ModelChoiceField(label=_("Tarif"), queryset=Plan.objects.filter(is_active=True))
    days = forms.IntegerField(label=_("Necha kunga"), min_value=1, max_value=3650, initial=30)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(is_phone_verified=True).order_by("full_name")


# ------------------------------------------------------------------ Kontent
class BannerForm(TranslationMixin, forms.ModelForm):
    class Meta:
        model = Banner
        fields = (
            "title", "subtitle", "image", "button_text", "button_url",
            "placement", "starts_at", "ends_at", "is_active", "order",
        )
        widgets = {
            "subtitle": forms.Textarea(attrs={"rows": 3}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "input"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "input"}),
        }


class NotificationForm(TranslationMixin, forms.ModelForm):
    class Meta:
        model = Notification
        fields = ("title", "body", "image", "audience", "course", "send_push", "send_telegram")
        widgets = {"body": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].required = False
        self.fields["course"].queryset = Course.objects.filter(is_active=True).order_by("title")

    def clean(self):
        data = super().clean()
        if data.get("audience") == Notification.AUDIENCE_COURSE and not data.get("course"):
            self.add_error("course", _("Kursni tanlang."))
        return data


class SiteSettingForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = (
            "site_name", "tagline", "support_phone", "support_telegram",
            "instagram", "youtube", "android_url", "ios_url", "terms_url",
            "default_language", "maintenance_mode",
        )
        widgets = {"default_language": forms.Select(choices=LANGUAGES, attrs={"class": "select"})}


# ------------------------------------------------------------------ Foydalanuvchilar
class UserForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "full_name", "phone", "role", "subject", "region", "district",
            "school", "grade", "birth_date", "avatar", "is_active",
        )
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date", "class": "input"})}


class AdminUserForm(StyledFormMixin, forms.ModelForm):
    """Yangi administrator qo'shish / tahrirlash."""

    password = forms.CharField(
        label=_("Parol"), required=False, widget=forms.PasswordInput(attrs={"class": "input"}),
        help_text=_("Tahrirlashda bo'sh qoldirilsa, parol o'zgarmaydi."),
    )

    class Meta:
        model = User
        fields = ("full_name", "phone", "avatar", "is_staff", "is_superuser", "is_active")

    def clean_phone(self):
        from accounts.utils import normalize_phone
        phone = normalize_phone(self.cleaned_data["phone"])
        if not phone:
            raise forms.ValidationError(_("Telefon raqam noto'g'ri."))
        qs = User.objects.filter(phone=phone).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("Bu raqam band."))
        return phone

    def clean(self):
        data = super().clean()
        if not self.instance.pk and not data.get("password"):
            self.add_error("password", _("Yangi admin uchun parol kiriting."))
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.ROLE_ADMIN
        user.is_phone_verified = True
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class PanelLoginForm(StyledFormMixin, forms.Form):
    phone = forms.CharField(label=_("Telefon raqam"),
                            widget=forms.TextInput(attrs={"class": "input", "placeholder": "+998 90 123 45 67",
                                                          "autofocus": "autofocus"}))
    password = forms.CharField(label=_("Parol"), widget=forms.PasswordInput(attrs={"class": "input"}))
