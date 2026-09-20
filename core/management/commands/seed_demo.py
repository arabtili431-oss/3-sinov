"""Panelni sinash uchun namunaviy ma'lumotlar.

Ishlatish:  python manage.py seed_demo
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from billing.models import Payment, Plan, Subscription
from core.models import Banner, Notification, SiteSetting
from courses.models import Category, Course, Enrollment, Lesson, Module
from shop.models import Order, OrderItem, Product, ProductCategory

User = get_user_model()

REGIONS = ["Toshkent shahri", "Farg'ona viloyati", "Samarqand viloyati", "Andijon viloyati",
           "Buxoro viloyati", "Namangan viloyati"]
NAMES = ["Sharofiddinov Xusniddin", "Karimova Nilufar", "Toshmatov Sardor", "Yo'ldosheva Malika",
         "Rahimov Bekzod", "Ergasheva Dilnoza", "Qodirov Jasur", "Umarova Zilola",
         "Nazarov Otabek", "Sultonova Feruza", "Ismoilov Aziz", "Xolmatova Sevara"]
COURSES = [
    ("Kompyuter savodxonligi", "Dasturlash", "free", 0),
    ("AI kontent yaratish", "Dizayn", "premium", 0),
    ("Grafik dizayn", "Dizayn", "premium", 0),
    ("UI/UX dizayn", "Dizayn", "paid", 490000),
    ("Scratch 3 dasturi", "Dasturlash", "free", 0),
    ("No-coding platformalar", "Dasturlash", "premium", 0),
    ("Kiber xavfsizlik asoslari", "Kiber xavfsizlik", "paid", 690000),
]
PRODUCTS = [("VECTOR futbolka", 149000, 40), ("VECTOR kepka", 89000, 25),
            ("Daftar to'plami", 45000, 120), ("Stiker to'plami", 25000, 0),
            ("Termos", 189000, 12)]


class Command(BaseCommand):
    help = "Namunaviy ma'lumotlarni yaratadi (faqat sinov uchun)"

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=40)

    def handle(self, *args, **options):
        SiteSetting.get()
        now = timezone.now()

        # --- Kategoriyalar va kurslar ---
        categories = {}
        for i, (name, icon, color) in enumerate([
            ("Dasturlash", "💻", "#1f6feb"), ("Dizayn", "🎨", "#ff6a00"),
            ("Kiber xavfsizlik", "🛡️", "#16a34a"), ("Marketing", "📣", "#8b5cf6"),
        ]):
            cat, _ = Category.objects.get_or_create(
                name=name, defaults={"icon": icon, "color": color, "order": i})
            categories[name] = cat

        teacher, _ = User.objects.get_or_create(
            phone="+998901112233",
            defaults={"full_name": "Sharofiddinov Xusniddin", "role": User.ROLE_TEACHER,
                      "subject": "Dasturlash", "is_active": True, "is_phone_verified": True},
        )

        for title, cat_name, access, price in COURSES:
            course, created = Course.objects.get_or_create(
                title=title,
                defaults={
                    "category": categories.get(cat_name),
                    "teacher": teacher,
                    "access": access,
                    "price": Decimal(price),
                    "short_description": f"{title} bo'yicha to'liq video kurs",
                    "description": f"{title} kursida siz noldan boshlab amaliy ko'nikmalarni egallaysiz.",
                    "is_active": True,
                    "is_featured": random.choice([True, False]),
                },
            )
            if created:
                for m in range(1, random.randint(3, 5)):
                    module = Module.objects.create(course=course, title=f"{m}-modul", order=m)
                    for l in range(1, random.randint(3, 6)):
                        Lesson.objects.create(
                            module=module, title=f"{l}-dars", order=l,
                            duration=random.randint(300, 2400),
                            is_free=(m == 1 and l == 1),
                            video_source=Lesson.VIDEO_NONE,
                        )

        # --- Tariflar ---
        for code, name, price, days, popular in [
            ("start", "START", 324000, 365, False),
            ("pro", "PRO", 444000, 365, True),
            ("vip", "VIP", 564000, 365, False),
        ]:
            Plan.objects.get_or_create(code=code, defaults={
                "name": name, "price": Decimal(price), "duration_days": days,
                "period": Plan.PERIOD_YEAR, "is_popular": popular,
                "features_text": "Juda oddiy - har oyda qayta to'lov\n"
                                 "Vector ni sinab ko'rish uchun qulay\n"
                                 "Barcha yo'nalish bo'yicha videodarslar\n"
                                 "Kurs yakunida sertifikat",
            })

        # --- Do'kon ---
        shop_cat, _ = ProductCategory.objects.get_or_create(name="Merch")
        for name, price, stock in PRODUCTS:
            Product.objects.get_or_create(name=name, defaults={
                "price": Decimal(price), "stock": stock, "category": shop_cat, "is_active": True})

        # --- Foydalanuvchilar ---
        plans = list(Plan.objects.all())
        courses = list(Course.objects.all())
        products = list(Product.objects.all())
        created_users = 0

        for i in range(options["users"]):
            phone = f"+9989{random.randint(10000000, 99999999)}"
            if User.objects.filter(phone=phone).exists():
                continue
            joined = now - timedelta(days=random.randint(0, 29), hours=random.randint(0, 23))
            user = User.objects.create(
                phone=phone,
                full_name=random.choice(NAMES),
                role=User.ROLE_STUDENT,
                region=random.choice(REGIONS),
                district="Markaz",
                school=f"{random.randint(1, 60)}-maktab",
                grade=f"{random.randint(5, 11)}-{random.choice('ABV')} sinf",
                is_active=True,
                is_phone_verified=True,
                date_joined=joined,
                last_login=joined if random.random() < 0.5 else now,
            )
            user.set_password("demo12345")
            user.save()
            created_users += 1

            for course in random.sample(courses, k=min(len(courses), random.randint(1, 3))):
                Enrollment.objects.get_or_create(
                    user=user, course=course,
                    defaults={"progress": random.randint(0, 100), "created_at": joined},
                )

            # Premium obuna
            if random.random() < 0.35 and plans:
                plan = random.choice(plans)
                sub = Subscription.objects.create(user=user, plan=plan, amount=plan.price)
                sub.activate()
                payment = Payment.objects.create(
                    user=user, amount=plan.price, provider=random.choice(["payme", "click"]),
                    target_type=Payment.TARGET_SUBSCRIPTION, target_id=sub.pk,
                    state=Payment.STATE_PAID,
                )
                Payment.objects.filter(pk=payment.pk).update(
                    created_at=joined + timedelta(hours=random.randint(1, 40)))

            # Do'kon buyurtmasi
            if random.random() < 0.25 and products:
                order = Order.objects.create(
                    user=user, full_name=user.full_name, phone=user.phone,
                    address=f"{user.region}, {user.district}",
                    status=random.choice([Order.STATUS_NEW, Order.STATUS_PAID, Order.STATUS_DONE]),
                )
                for product in random.sample(products, k=random.randint(1, 2)):
                    OrderItem.objects.create(order=order, product=product,
                                             product_name=product.name, price=product.price,
                                             quantity=random.randint(1, 3))
                order.recalculate()
                Order.objects.filter(pk=order.pk).update(created_at=joined)
                if order.status != Order.STATUS_NEW:
                    Payment.objects.create(
                        user=user, amount=order.total, provider="click",
                        target_type=Payment.TARGET_ORDER, target_id=order.pk,
                        state=Payment.STATE_PAID,
                    )

        # --- Banner va bildirishnoma ---
        Banner.objects.get_or_create(title="Targ'ibotchilar", defaults={
            "subtitle": "Do'stlaringizni Ustoz AI'ga taklif qiling va Premium imkoniyatlardan foydalaning.",
            "button_text": "Yechimni olish", "button_url": "/premium/", "is_active": True})
        Notification.objects.get_or_create(title="Yangi kurs qo'shildi!", defaults={
            "body": "Grafik dizayn kursi platformaga qo'shildi. Hoziroq ko'rishni boshlang.",
            "audience": Notification.AUDIENCE_ALL})

        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: {created_users} foydalanuvchi, {Course.objects.count()} kurs, "
            f"{Lesson.objects.count()} dars, {Product.objects.count()} mahsulot, "
            f"{Payment.objects.filter(state='paid').count()} to'lov."
        ))
