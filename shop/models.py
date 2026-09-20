"""Do'kon: mahsulotlar, buyurtmalar."""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.i18n import TranslatableMixin
from core.models import TimeStampedModel


class ProductCategory(TranslatableMixin, models.Model):
    translatable_fields = ("name",)

    name = models.CharField("Nomi", max_length=80)
    slug = models.SlugField("Slug", max_length=100, unique=True, blank=True)
    order = models.PositiveIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Aktiv", default=True)

    class Meta:
        verbose_name = "Mahsulot kategoriyasi"
        verbose_name_plural = "Mahsulot kategoriyalari"
        ordering = ("order", "name")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "kategoriya"
            slug, i = base, 2
            while ProductCategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Product(TranslatableMixin, TimeStampedModel):
    """Do'kondagi mahsulot: futbolka, kepka, daftar va h.k."""

    translatable_fields = ("name", "description")

    name = models.CharField("Mahsulot nomi", max_length=140)
    slug = models.SlugField("Slug", max_length=160, unique=True, blank=True)
    description = models.TextField("Tavsif", blank=True)
    image = models.ImageField("Rasmi", upload_to="products/", blank=True)
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="products", verbose_name="Kategoriya")

    price = models.DecimalField("Narxi (so'm)", max_digits=12, decimal_places=2, default=0)
    old_price = models.DecimalField("Eski narxi", max_digits=12, decimal_places=2, default=0)
    coin_price = models.PositiveIntegerField(
        "Narxi (Coin)", default=0,
        help_text="0 bo'lsa — mahsulot Coin do'konida (Sovg'a bo'limida) ko'rinmaydi.",
    )
    stock = models.IntegerField("Qoldiq soni", default=0)
    sku = models.CharField("Artikul", max_length=40, blank=True)

    is_active = models.BooleanField("Sotuvda", default=True)
    is_featured = models.BooleanField("Tavsiya etilgan", default=False)
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        ordering = ("order", "-created_at")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "mahsulot"
            slug, i = base, 2
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def discount_percent(self):
        if self.old_price and self.old_price > self.price:
            return round((1 - float(self.price) / float(self.old_price)) * 100)
        return 0

    @property
    def is_coin_item(self):
        return self.coin_price > 0

    @property
    def average_rating(self):
        agg = self.reviews.aggregate(models.Avg("rating"))
        return round(agg["rating__avg"] or 0, 1)

    @property
    def reviews_count(self):
        return self.reviews.count()


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("Rasm", upload_to="products/")
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Mahsulot rasmi"
        verbose_name_plural = "Mahsulot rasmlari"
        ordering = ("order", "id")


class Order(TimeStampedModel):
    """Do'kon buyurtmasi."""

    STATUS_NEW = "new"
    STATUS_PAID = "paid"
    STATUS_SHIPPED = "shipped"
    STATUS_DONE = "done"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_NEW, _("Yangi")),
        (STATUS_PAID, _("To'langan")),
        (STATUS_SHIPPED, _("Yuborilgan")),
        (STATUS_DONE, _("Yakunlangan")),
        (STATUS_CANCELLED, _("Bekor qilingan")),
    ]

    number = models.CharField("Buyurtma raqami", max_length=20, unique=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                             related_name="orders", verbose_name="Foydalanuvchi")
    full_name = models.CharField("Qabul qiluvchi", max_length=120)
    phone = models.CharField("Telefon", max_length=20)
    address = models.TextField("Manzil", blank=True)
    comment = models.TextField("Izoh", blank=True)

    total = models.DecimalField("Umumiy summa", max_digits=14, decimal_places=2, default=0)
    status = models.CharField("Holat", max_length=12, choices=STATUS_CHOICES, default=STATUS_NEW)
    paid_at = models.DateTimeField("To'langan vaqt", null=True, blank=True)
    paid_via_coin = models.BooleanField("Coin orqali to'langan", default=False)
    coin_total = models.PositiveIntegerField("Umumiy Coin", default=0)

    class Meta:
        verbose_name = "Buyurtma"
        verbose_name_plural = "Buyurtmalar"
        ordering = ("-created_at",)

    def __str__(self):
        return self.number or f"Buyurtma #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = timezone.now().strftime("%y%m%d") + get_random_string(4, "0123456789")
        super().save(*args, **kwargs)

    def recalculate(self):
        self.total = sum((i.price * i.quantity for i in self.items.all()), start=0)
        self.save(update_fields=["total"])
        return self.total

    def mark_paid(self):
        self.status = self.STATUS_PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at"])
        for item in self.items.select_related("product"):
            if item.product:
                item.product.stock = max(0, item.product.stock - item.quantity)
                item.product.save(update_fields=["stock"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name="order_items")
    product_name = models.CharField("Mahsulot nomi", max_length=140)
    price = models.DecimalField("Narxi", max_digits=12, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField("Soni", default=1)

    class Meta:
        verbose_name = "Buyurtma qatori"
        verbose_name_plural = "Buyurtma qatorlari"

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

    @property
    def subtotal(self):
        return self.price * self.quantity

    def save(self, *args, **kwargs):
        if self.product and not self.product_name:
            self.product_name = self.product.name
        if self.product and not self.price:
            self.price = self.product.price
        super().save(*args, **kwargs)


class ProductReview(TimeStampedModel):
    """Mahsulotga qoldirilgan sharh (yulduzcha baho + izoh)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_reviews")
    rating = models.PositiveSmallIntegerField("Baho (1-5)", default=5)
    comment = models.TextField("Izoh", blank=True)

    class Meta:
        verbose_name = "Mahsulot sharhi"
        verbose_name_plural = "Mahsulot sharhlari"
        unique_together = ("product", "user")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.full_name} — {self.product.name} ({self.rating}★)"
