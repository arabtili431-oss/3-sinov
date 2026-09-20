"""Mobil ilova uchun API serializerlari."""
from rest_framework import serializers

from billing.models import Plan, Subscription
from core.models import Banner, Notification, NotificationDelivery
from courses.models import (
    Category,
    Course,
    Lesson,
    LessonAttachment,
    LessonQuiz,
    Module,
    QuizChoice,
    QuizQuestion,
)
from shop.models import Order, OrderItem, Product, ProductCategory, ProductReview


class TranslatedField(serializers.Field):
    """Joriy tildagi matnni qaytaradi."""

    def __init__(self, field_name, **kwargs):
        self.source_field = field_name
        kwargs["source"] = "*"
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def to_representation(self, instance):
        language = self.context.get("language")
        return instance.t(self.source_field, language)


class CategorySerializer(serializers.ModelSerializer):
    name = TranslatedField("name")

    class Meta:
        model = Category
        fields = ("id", "slug", "name", "icon", "color", "image", "order")


class CourseShortSerializer(serializers.ModelSerializer):
    title = TranslatedField("title")
    short_description = TranslatedField("short_description")
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    teacher = serializers.CharField(source="teacher_display", read_only=True)
    lessons_count = serializers.IntegerField(read_only=True)
    students_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = (
            "id", "slug", "title", "short_description", "cover", "category", "category_name",
            "teacher", "access", "price", "old_price", "level", "is_featured",
            "lessons_count", "students_count",
        )


class LessonShortSerializer(serializers.ModelSerializer):
    title = TranslatedField("title")
    is_locked = serializers.SerializerMethodField()
    duration_display = serializers.CharField(read_only=True)

    class Meta:
        model = Lesson
        fields = ("id", "title", "duration", "duration_display", "is_free", "is_locked",
                  "thumbnail", "order")

    def get_is_locked(self, obj):
        return obj.is_locked_for(self.context.get("request").user if self.context.get("request") else None)


class ModuleSerializer(serializers.ModelSerializer):
    title = TranslatedField("title")
    lessons = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ("id", "title", "order", "lessons")

    def get_lessons(self, obj):
        qs = obj.lessons.filter(is_active=True).order_by("order")
        return LessonShortSerializer(qs, many=True, context=self.context).data


class CourseDetailSerializer(CourseShortSerializer):
    description = TranslatedField("description")
    modules = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    my_progress = serializers.SerializerMethodField()

    class Meta(CourseShortSerializer.Meta):
        fields = CourseShortSerializer.Meta.fields + (
            "description", "modules", "is_available", "my_progress", "total_duration",
        )

    def get_modules(self, obj):
        qs = obj.modules.filter(is_active=True).order_by("order")
        return ModuleSerializer(qs, many=True, context=self.context).data

    def get_is_available(self, obj):
        request = self.context.get("request")
        return obj.is_available_for(request.user if request else None)

    def get_my_progress(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0
        enrollment = obj.enrollments.filter(user=request.user).first()
        return enrollment.progress if enrollment else 0


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonAttachment
        fields = ("id", "title", "file", "size")


class LessonDetailSerializer(serializers.ModelSerializer):
    title = TranslatedField("title")
    description = TranslatedField("description")
    text = TranslatedField("text")
    attachments = AttachmentSerializer(many=True, read_only=True)
    video = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()
    course_id = serializers.IntegerField(source="module.course_id", read_only=True)

    has_quiz = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ("id", "course_id", "title", "description", "text", "duration",
                  "thumbnail", "is_free", "is_locked", "video", "attachments", "has_quiz")

    def get_has_quiz(self, obj):
        return LessonQuiz.objects.filter(lesson=obj, is_active=True, questions__isnull=False).exists()

    def get_is_locked(self, obj):
        request = self.context.get("request")
        return obj.is_locked_for(request.user if request else None)

    def get_video(self, obj):
        """Qulflangan dars uchun video havolasi berilmaydi."""
        request = self.context.get("request")
        user = request.user if request else None
        if obj.is_locked_for(user):
            return None
        if obj.telegram_file_id:
            from core.signing import make_video_token
            token = make_video_token(obj.pk, getattr(user, "pk", 0))
            url = f"/api/lessons/{obj.pk}/video/?t={token}"
            return {"type": "stream", "url": request.build_absolute_uri(url) if request else url}
        if obj.video_url:
            return {"type": "url", "url": obj.video_url}
        return None


class PlanSerializer(serializers.ModelSerializer):
    name = TranslatedField("name")
    description = TranslatedField("description")
    features = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = ("id", "code", "name", "description", "features", "price", "old_price",
                  "period", "duration_days", "is_popular", "color")

    def get_features(self, obj):
        return obj.features_for(self.context.get("language"))


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ("id", "plan", "plan_name", "amount", "status", "starts_at", "ends_at", "days_left")
        read_only_fields = fields


class ProductSerializer(serializers.ModelSerializer):
    name = TranslatedField("name")
    description = TranslatedField("description")
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    category_slug = serializers.CharField(source="category.slug", read_only=True, default="")

    class Meta:
        model = Product
        fields = ("id", "slug", "name", "description", "image", "category", "category_name", "category_slug",
                  "price", "old_price", "coin_price", "is_coin_item", "stock", "in_stock",
                  "discount_percent", "is_featured", "average_rating", "reviews_count")


class ProductReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_avatar = serializers.ImageField(source="user.avatar", read_only=True, use_url=True)

    class Meta:
        model = ProductReview
        fields = ("id", "user_name", "user_avatar", "rating", "comment", "created_at")
        read_only_fields = ("id", "user_name", "user_avatar", "created_at")

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Baho 1 dan 5 gacha bo'lishi kerak.")
        return value


class ProductCategorySerializer(serializers.ModelSerializer):
    name = TranslatedField("name")

    class Meta:
        model = ProductCategory
        fields = ("id", "slug", "name", "order")


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("id", "product", "product_name", "price", "quantity", "subtotal")
        read_only_fields = ("id", "product_name", "price", "subtotal")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ("id", "number", "full_name", "phone", "address", "comment",
                  "total", "status", "items", "created_at")
        read_only_fields = ("number", "total", "status", "created_at")

    def create(self, validated_data):
        items = validated_data.pop("items", [])
        order = Order.objects.create(**validated_data)
        for item in items:
            product = item.get("product")
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name if product else "",
                price=product.price if product else 0,
                quantity=item.get("quantity", 1),
            )
        order.recalculate()
        return order


class QuizChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizChoice
        fields = ("id", "text")  # is_correct hech qachon frontendga yuborilmaydi


class QuizQuestionSerializer(serializers.ModelSerializer):
    choices = QuizChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = QuizQuestion
        fields = ("id", "text", "choices")


class LessonQuizSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    attempted = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()

    class Meta:
        model = LessonQuiz
        fields = ("id", "coin_reward", "pass_percent", "questions", "attempted", "result")

    def get_questions(self, obj):
        qs = obj.questions.prefetch_related("choices").order_by("order", "id")
        return QuizQuestionSerializer(qs, many=True).data

    def _attempt(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        return obj.attempts.filter(user=request.user).first()

    def get_attempted(self, obj):
        return self._attempt(obj) is not None

    def get_result(self, obj):
        attempt = self._attempt(obj)
        if not attempt:
            return None
        return {
            "score_percent": attempt.score_percent,
            "correct_count": attempt.correct_count,
            "total_count": attempt.total_count,
            "coins_earned": attempt.coins_earned,
        }


class BannerSerializer(serializers.ModelSerializer):
    title = TranslatedField("title")
    subtitle = TranslatedField("subtitle")
    button_text = TranslatedField("button_text")

    class Meta:
        model = Banner
        fields = ("id", "title", "subtitle", "image", "button_text", "button_url", "placement")


class NotificationSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    sent_at = serializers.DateTimeField(source="notification.sent_at", read_only=True)

    class Meta:
        model = NotificationDelivery
        fields = ("id", "title", "body", "image", "is_read", "sent_at", "created_at")

    def _lang(self):
        return self.context.get("language")

    def get_title(self, obj):
        return obj.notification.t("title", self._lang())

    def get_body(self, obj):
        return obj.notification.t("body", self._lang())

    def get_image(self, obj):
        image = obj.notification.image
        if not image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(image.url) if request else image.url
