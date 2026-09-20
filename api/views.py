"""Mobil ilova uchun ochiq API."""
from django.db.models import Count, Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model

from billing.models import Payment, Plan, PromoCode, Subscription
from core.models import Banner, NotificationDelivery, SiteSetting
from core.services import telegram_files
from core.signing import read_video_token
from courses.models import Category, Course, Enrollment, Lesson, LessonProgress, LessonQuiz, QuizAttempt
from shop.models import Order, OrderItem, Product, ProductCategory, ProductReview

from .serializers import (
    BannerSerializer,
    CategorySerializer,
    CourseDetailSerializer,
    CourseShortSerializer,
    LessonDetailSerializer,
    LessonQuizSerializer,
    NotificationSerializer,
    OrderSerializer,
    PlanSerializer,
    ProductCategorySerializer,
    ProductReviewSerializer,
    ProductSerializer,
    SubscriptionSerializer,
)


class LanguageMixin:
    """`?lang=ru` yoki Accept-Language sarlavhasidan tilni oladi."""

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["language"] = self.request.GET.get("lang") or self.request.LANGUAGE_CODE
        return context


# ------------------------------------------------------------------ Kurslar
class CategoryListView(LanguageMixin, ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None
    queryset = Category.objects.filter(is_active=True).order_by("order", "name")


class CourseListView(LanguageMixin, ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CourseShortSerializer

    def get_queryset(self):
        qs = Course.objects.filter(is_active=True).select_related("category", "teacher")
        params = self.request.GET
        if params.get("category"):
            qs = qs.filter(category__slug=params["category"])
        if params.get("access"):
            qs = qs.filter(access=params["access"])
        if params.get("featured"):
            qs = qs.filter(is_featured=True)
        if params.get("q"):
            qs = qs.filter(Q(title__icontains=params["q"]) | Q(short_description__icontains=params["q"]))
        return qs.order_by("order", "-created_at")


class CourseDetailView(LanguageMixin, RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = CourseDetailSerializer
    lookup_field = "slug"
    queryset = Course.objects.filter(is_active=True)


class LessonDetailView(LanguageMixin, RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = LessonDetailSerializer
    queryset = Lesson.objects.filter(is_active=True).select_related("module__course")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def enroll(request, slug):
    """Kursga yozilish."""
    course = get_object_or_404(Course, slug=slug, is_active=True)
    if not course.is_available_for(request.user):
        return Response(
            {"detail": "Bu kurs uchun premium obuna yoki to'lov kerak.", "code": "payment_required"},
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )
    enrollment, created = Enrollment.objects.get_or_create(user=request.user, course=course)
    enrollment.last_opened_at = timezone.now()
    enrollment.save(update_fields=["last_opened_at"])
    return Response({"enrolled": True, "created": created, "progress": enrollment.progress})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def lesson_complete(request, pk):
    """Darsni tugatilgan deb belgilash."""
    lesson = get_object_or_404(Lesson, pk=pk, is_active=True)
    if lesson.is_locked_for(request.user):
        return Response({"detail": "Dars qulflangan."}, status=403)

    progress, _created = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)
    progress.is_completed = bool(request.data.get("completed", True))
    progress.seconds_watched = int(request.data.get("seconds", progress.seconds_watched) or 0)
    progress.save()

    enrollment, _ = Enrollment.objects.get_or_create(user=request.user, course=lesson.module.course)
    return Response({"progress": enrollment.recalculate()})


@api_view(["GET"])
@permission_classes([AllowAny])
def lesson_quiz(request, pk):
    """Darsga tegishli testni qaytaradi (to'g'ri javoblarsiz)."""
    lesson = get_object_or_404(Lesson, pk=pk, is_active=True)
    quiz = LessonQuiz.objects.filter(lesson=lesson, is_active=True).first()
    if not quiz or not quiz.questions.exists():
        return Response({"detail": "Bu dars uchun test yo'q."}, status=404)
    return Response(LessonQuizSerializer(quiz, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def lesson_quiz_submit(request, pk):
    """Test javoblarini qabul qiladi, natijaga qarab Coin beradi (faqat 1-marta)."""
    lesson = get_object_or_404(Lesson, pk=pk, is_active=True)
    quiz = LessonQuiz.objects.filter(lesson=lesson, is_active=True).prefetch_related(
        "questions__choices"
    ).first()
    if not quiz or not quiz.questions.exists():
        return Response({"detail": "Bu dars uchun test yo'q."}, status=404)

    existing = QuizAttempt.objects.filter(user=request.user, quiz=quiz).first()
    if existing:
        return Response({
            "detail": "Siz bu testni allaqachon yechgansiz.",
            "score_percent": existing.score_percent,
            "correct_count": existing.correct_count,
            "total_count": existing.total_count,
            "coins_earned": existing.coins_earned,
        }, status=200)

    answers = request.data.get("answers") or {}
    questions = list(quiz.questions.all())
    total = len(questions)
    correct = 0
    for question in questions:
        chosen_id = answers.get(str(question.id)) or answers.get(question.id)
        if chosen_id is None:
            continue
        is_correct = question.choices.filter(pk=chosen_id, is_correct=True).exists()
        if is_correct:
            correct += 1

    score_percent = round((correct / total) * 100) if total else 0
    coins_earned = round(quiz.coin_reward * score_percent / 100)

    attempt = QuizAttempt.objects.create(
        user=request.user, quiz=quiz, score_percent=score_percent,
        correct_count=correct, total_count=total, coins_earned=coins_earned,
    )
    if coins_earned:
        request.user.add_coins(coins_earned)

    return Response({
        "score_percent": attempt.score_percent,
        "correct_count": attempt.correct_count,
        "total_count": attempt.total_count,
        "coins_earned": attempt.coins_earned,
        "coins_balance": request.user.coins,
        "passed": score_percent >= quiz.pass_percent,
    }, status=201)


@api_view(["GET"])
@permission_classes([AllowAny])
def leaderboard(request):
    """Coin bo'yicha reyting (top 50 o'quvchi)."""
    User = get_user_model()
    qs = (User.objects.filter(role=User.ROLE_STUDENT, is_active=True, coins__gt=0)
          .order_by("-coins")[:50])
    data = []
    for rank, user in enumerate(qs, start=1):
        data.append({
            "rank": rank,
            "id": user.id,
            "full_name": user.full_name,
            "avatar": request.build_absolute_uri(user.avatar.url) if user.avatar else None,
            "coins": user.coins,
            "is_me": request.user.is_authenticated and request.user.pk == user.pk,
        })
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_courses(request):
    """Foydalanuvchi yozilgan kurslar."""
    qs = Course.objects.filter(enrollments__user=request.user).select_related("category")
    data = CourseShortSerializer(qs, many=True, context={"request": request,
                                                         "language": request.GET.get("lang")}).data
    progress = {e.course_id: e.progress for e in Enrollment.objects.filter(user=request.user)}
    for item in data:
        item["my_progress"] = progress.get(item["id"], 0)
    return Response(data)


class LessonVideoView(APIView):
    """Videoni Telegramdan oqim ko'rinishida uzatadi.

    Havola qisqa muddatli va imzolangan — token boshqa foydalanuvchida ishlamaydi.
    """

    permission_classes = [AllowAny]

    def get(self, request, pk):
        token = request.GET.get("t", "")
        payload = read_video_token(token)
        if not payload:
            return Response({"detail": "Havola eskirgan yoki noto'g'ri."}, status=403)

        lesson_id, user_id = payload
        if int(lesson_id) != int(pk):
            return Response({"detail": "Havola bu darsga tegishli emas."}, status=403)
        if request.user.is_authenticated and request.user.pk != user_id:
            return Response({"detail": "Havola boshqa foydalanuvchi uchun."}, status=403)

        lesson = get_object_or_404(Lesson, pk=pk, is_active=True)
        if not lesson.telegram_file_id:
            return Response({"detail": "Video topilmadi."}, status=404)

        try:
            stream, content_type, code, headers = telegram_files.stream_file(
                lesson.telegram_file_id,
                range_header=request.headers.get("Range"),
                file_size=lesson.video_size,
            )
        except telegram_files.TelegramStorageError as exc:
            return Response({"detail": str(exc)}, status=502)

        response = StreamingHttpResponse(stream, content_type=content_type, status=code)
        for key, value in headers.items():
            response[key] = value
        response["Accept-Ranges"] = "bytes"
        response["Cache-Control"] = "private, max-age=0, no-store"
        response["Content-Disposition"] = "inline"
        return response


# ------------------------------------------------------------------- Premium
class PlanListView(LanguageMixin, ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PlanSerializer
    pagination_class = None
    queryset = Plan.objects.filter(is_active=True).order_by("order", "price")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_subscription(request):
    sub = request.user.active_subscription
    if not sub:
        return Response({"active": False})
    return Response({"active": True, **SubscriptionSerializer(sub).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def subscribe(request):
    """Obuna yaratadi va to'lov havolalarini qaytaradi.

    Foydalanuvchi ro'yxatdan o'tishda promo kod kiritgan bo'lsa va uni hali
    ishlatmagan bo'lsa — birinchi Premium xaridida bir martalik chegirma
    avtomatik qo'llaniladi.
    """
    from billing.services import checkout_links

    plan = get_object_or_404(Plan, pk=request.data.get("plan"), is_active=True)
    amount = plan.price
    promo = None
    if request.user.promo_code_used and not request.user.promo_discount_applied:
        promo = PromoCode.objects.filter(code=request.user.promo_code_used, is_active=True).first()
        if promo and promo.is_usable:
            amount = promo.apply_to(amount)
        else:
            promo = None

    subscription = Subscription.objects.create(
        user=request.user, plan=plan, amount=amount, promo_code=promo,
    )
    payment = Payment.objects.create(
        user=request.user,
        amount=amount,
        target_type=Payment.TARGET_SUBSCRIPTION,
        target_id=subscription.pk,
        provider=request.data.get("provider") or Payment.PROVIDER_PAYME,
    )
    if promo:
        promo.mark_used()
        request.user.promo_discount_applied = True
        request.user.save(update_fields=["promo_discount_applied"])

    return Response({
        "subscription": SubscriptionSerializer(subscription).data,
        "payment_reference": payment.reference,
        "checkout": checkout_links(payment, request),
        "promo_applied": bool(promo),
        "discount_percent": promo.discount_percent if promo else 0,
    }, status=201)


# --------------------------------------------------------------------- Do'kon
class ProductListView(LanguageMixin, ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).select_related("category")
        params = self.request.GET
        if params.get("category"):
            qs = qs.filter(category__slug=params["category"])
        if params.get("q"):
            qs = qs.filter(name__icontains=params["q"])
        return qs.order_by("order", "-created_at")


class ProductDetailView(LanguageMixin, RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    lookup_field = "slug"
    queryset = Product.objects.filter(is_active=True)


class ProductCategoryListView(LanguageMixin, ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductCategorySerializer
    pagination_class = None
    queryset = ProductCategory.objects.filter(is_active=True).order_by("order")


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def product_reviews(request, slug):
    """GET — mahsulot sharhlari ro'yxati. POST — yangi sharh qoldirish (tizimga kirgan bo'lsa)."""
    product = get_object_or_404(Product, slug=slug, is_active=True)

    if request.method == "GET":
        qs = product.reviews.select_related("user").order_by("-created_at")
        return Response({
            "average_rating": product.average_rating,
            "reviews_count": product.reviews_count,
            "results": ProductReviewSerializer(qs, many=True, context={"request": request}).data,
        })

    if not request.user.is_authenticated:
        return Response({"detail": "Sharh qoldirish uchun tizimga kiring."}, status=401)

    serializer = ProductReviewSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    review, _created = ProductReview.objects.update_or_create(
        product=product, user=request.user,
        defaults={
            "rating": serializer.validated_data["rating"],
            "comment": serializer.validated_data.get("comment", ""),
        },
    )
    return Response(ProductReviewSerializer(review, context={"request": request}).data, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def product_redeem(request, slug):
    """Mahsulotni Coin evaziga darhol xarid qilish ('Hoziroq xarid qilish')."""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    if not product.is_coin_item:
        return Response({"detail": "Bu mahsulot Coin evaziga sotilmaydi."}, status=400)

    quantity = max(1, int(request.data.get("quantity", 1) or 1))
    if product.stock < quantity:
        return Response({"detail": "Omborda yetarli mahsulot yo'q."}, status=400)

    cost = product.coin_price * quantity
    if request.user.coins < cost:
        return Response({
            "detail": f"Coin yetarli emas. Kerak: {cost}, mavjud: {request.user.coins}.",
        }, status=400)

    order = Order.objects.create(
        user=request.user, full_name=request.user.full_name, phone=request.user.phone,
        status=Order.STATUS_PAID, paid_via_coin=True, coin_total=cost,
    )
    OrderItem.objects.create(
        order=order, product=product, product_name=product.name,
        price=product.coin_price, quantity=quantity,
    )
    order.total = cost
    order.paid_at = timezone.now()
    order.save(update_fields=["total", "paid_at"])
    product.stock = max(0, product.stock - quantity)
    product.save(update_fields=["stock"])
    request.user.add_coins(-cost)

    return Response({
        "order": OrderSerializer(order).data,
        "coins_balance": request.user.coins,
    }, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order(request):
    """Do'kon buyurtmasini yaratadi va to'lov havolasini qaytaradi."""
    from billing.services import checkout_links

    serializer = OrderSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    order = serializer.save(user=request.user)

    payment = Payment.objects.create(
        user=request.user,
        amount=order.total,
        target_type=Payment.TARGET_ORDER,
        target_id=order.pk,
        provider=request.data.get("provider") or Payment.PROVIDER_PAYME,
    )
    return Response({
        "order": OrderSerializer(order).data,
        "payment_reference": payment.reference,
        "checkout": checkout_links(payment, request),
    }, status=201)


def _coin_cart(user):
    order, _ = Order.objects.get_or_create(
        user=user, status=Order.STATUS_NEW, paid_via_coin=True,
        defaults={"full_name": user.full_name, "phone": user.phone},
    )
    return order


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cart_view(request):
    """Foydalanuvchining Coin savatchasi (hali to'lanmagan buyurtma)."""
    order = _coin_cart(request.user)
    return Response(OrderSerializer(order).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cart_add(request):
    """Mahsulotni Coin savatchasiga qo'shadi ('Savatga qo'shish')."""
    product = get_object_or_404(Product, slug=request.data.get("slug"), is_active=True)
    if not product.is_coin_item:
        return Response({"detail": "Bu mahsulot Coin evaziga sotilmaydi."}, status=400)
    quantity = max(1, int(request.data.get("quantity", 1) or 1))

    order = _coin_cart(request.user)
    item, created = OrderItem.objects.get_or_create(
        order=order, product=product,
        defaults={"product_name": product.name, "price": product.coin_price, "quantity": quantity},
    )
    if not created:
        item.quantity += quantity
        item.save(update_fields=["quantity"])
    order.recalculate()
    return Response(OrderSerializer(order).data, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cart_remove(request):
    item_id = request.data.get("item_id")
    order = _coin_cart(request.user)
    order.items.filter(pk=item_id).delete()
    order.recalculate()
    return Response(OrderSerializer(order).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cart_checkout(request):
    """Savatchadagi barcha mahsulotlarni Coin evaziga rasmiylashtiradi."""
    order = _coin_cart(request.user)
    items = list(order.items.select_related("product"))
    if not items:
        return Response({"detail": "Savatcha bo'sh."}, status=400)

    cost = sum(int(i.price) * i.quantity for i in items)
    for i in items:
        if not i.product or i.product.stock < i.quantity:
            return Response({"detail": f"'{i.product_name}' omborda yetarli emas."}, status=400)
    if request.user.coins < cost:
        return Response({"detail": f"Coin yetarli emas. Kerak: {cost}, mavjud: {request.user.coins}."}, status=400)

    for i in items:
        i.product.stock = max(0, i.product.stock - i.quantity)
        i.product.save(update_fields=["stock"])

    order.status = Order.STATUS_PAID
    order.paid_at = timezone.now()
    order.coin_total = cost
    order.total = cost
    order.save(update_fields=["status", "paid_at", "coin_total", "total"])
    request.user.add_coins(-cost)

    return Response({"order": OrderSerializer(order).data, "coins_balance": request.user.coins})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_orders(request):
    qs = request.user.orders.prefetch_related("items").order_by("-created_at")
    return Response(OrderSerializer(qs, many=True).data)


# -------------------------------------------------------------- Bildirishnoma
class NotificationListView(LanguageMixin, ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return (NotificationDelivery.objects
                .filter(user=self.request.user, notification__status="sent")
                .select_related("notification")
                .order_by("-created_at"))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notification_read(request, pk):
    delivery = get_object_or_404(NotificationDelivery, pk=pk, user=request.user)
    delivery.mark_read()
    return Response({"is_read": True})


# -------------------------------------------------------------------- Umumiy
class BannerListView(LanguageMixin, ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = BannerSerializer
    pagination_class = None

    def get_queryset(self):
        now = timezone.now()
        qs = Banner.objects.filter(is_active=True).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now)
        ).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        placement = self.request.GET.get("placement")
        if placement:
            qs = qs.filter(placement=placement)
        return qs.order_by("order")


@api_view(["GET"])
@permission_classes([AllowAny])
def app_config(request):
    """Ilova ishga tushganda kerak bo'ladigan umumiy ma'lumotlar."""
    settings_obj = SiteSetting.get()
    return Response({
        "site_name": settings_obj.site_name,
        "tagline": settings_obj.tagline,
        "support_phone": settings_obj.support_phone,
        "support_telegram": settings_obj.support_telegram,
        "instagram": settings_obj.instagram,
        "youtube": settings_obj.youtube,
        "android_url": settings_obj.android_url,
        "ios_url": settings_obj.ios_url,
        "terms_url": settings_obj.terms_url,
        "maintenance_mode": settings_obj.maintenance_mode,
        "languages": ["uz", "uz-cyrl", "ru", "en"],
        "stats": {
            "courses": Course.objects.filter(is_active=True).count(),
            "lessons": Lesson.objects.filter(is_active=True).count(),
            "students": Enrollment.objects.values("user").distinct().count(),
        },
    })
