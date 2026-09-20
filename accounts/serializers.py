"""API serializerlari."""
from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import TelegramVerification, User
from .utils import normalize_phone


class PhoneField(serializers.CharField):
    """Telefon raqamni +998XXXXXXXXX ko'rinishiga keltiruvchi maydon."""

    def to_internal_value(self, data):
        raw = super().to_internal_value(data)
        phone = normalize_phone(raw)
        if not phone:
            raise serializers.ValidationError(
                "Telefon raqam noto'g'ri. Masalan: (90) 123-45-67"
            )
        return phone


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "phone", "full_name", "role", "role_display", "subject",
            "region", "district", "school", "grade", "birth_date",
            "telegram_username", "is_phone_verified", "date_joined",
            "coins", "avatar", "is_premium",
        )
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    phone = PhoneField(max_length=20)
    password = serializers.CharField(write_only=True, min_length=6, max_length=128)
    password2 = serializers.CharField(write_only=True, required=False)
    promo_code = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=40)

    class Meta:
        model = User
        fields = (
            "phone", "full_name", "role", "subject", "region", "district",
            "school", "grade", "birth_date", "password", "password2", "promo_code",
        )
        extra_kwargs = {
            "full_name": {"required": True, "allow_blank": False},
            "region": {"required": True, "allow_blank": False},
            "district": {"required": True, "allow_blank": False},
            "school": {"required": False, "allow_blank": True},
            "grade": {"required": False, "allow_blank": True},
            "birth_date": {"required": True},
            "subject": {"required": False, "allow_blank": True},
        }

    def validate_full_name(self, value):
        value = " ".join(value.split())
        if len(value.split(" ")) < 2:
            raise serializers.ValidationError("Ism va familiyani to'liq kiriting.")
        return value

    def validate_role(self, value):
        if value not in (User.ROLE_STUDENT, User.ROLE_TEACHER):
            raise serializers.ValidationError("Rol noto'g'ri tanlangan.")
        return value

    def validate(self, attrs):
        p2 = attrs.pop("password2", None)
        if p2 is not None and p2 != attrs.get("password"):
            raise serializers.ValidationError({"password2": "Parollar mos kelmadi."})

        role = attrs.get("role", User.ROLE_STUDENT)
        if role == User.ROLE_TEACHER:
            attrs["grade"] = ""
        else:
            attrs["subject"] = ""

        # Promo kod — noto'g'ri/eskirgan bo'lsa ham ro'yxatdan o'tishni to'xtatmaymiz,
        # shunchaki e'tiborsiz qoldiramiz (keyinroq Premium xaridida tekshiriladi).
        promo = (attrs.pop("promo_code", "") or "").strip().upper()
        attrs["promo_code_used"] = promo
        return attrs

    def validate_phone(self, phone):
        qs = User.objects.filter(phone=phone)
        if qs.filter(is_phone_verified=True).exists():
            raise serializers.ValidationError(
                "Bu raqam allaqachon ro'yxatdan o'tgan. Kirish sahifasidan foydalaning."
            )
        return phone

    def create(self, validated_data):
        password = validated_data.pop("password")
        phone = validated_data["phone"]
        # Tasdiqlanmagan eski yozuv bo'lsa — yangilaymiz, yangisini yaratmaymiz.
        user = User.objects.filter(phone=phone, is_phone_verified=False).first()
        if user:
            for field, value in validated_data.items():
                setattr(user, field, value)
            user.set_password(password)
            user.is_active = False
            user.save()
            return user
        return User.objects.create_user(password=password, **validated_data)


class VerifySerializer(serializers.Serializer):
    verification_id = serializers.UUIDField()
    code = serializers.CharField(min_length=4, max_length=8)


class ResendSerializer(serializers.Serializer):
    verification_id = serializers.UUIDField()


class LoginSerializer(serializers.Serializer):
    phone = PhoneField(max_length=20)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["phone"],
            password=attrs["password"],
        )
        if user is None:
            # Faol emas yoki parol xato — sababini aniqlaymiz
            exists = User.objects.filter(phone=attrs["phone"]).first()
            if exists and not exists.is_phone_verified:
                raise serializers.ValidationError(
                    {"detail": "Raqam Telegram orqali tasdiqlanmagan.", "code": "not_verified"}
                )
            raise serializers.ValidationError(
                {"detail": "Telefon raqam yoki parol noto'g'ri."}
            )
        attrs["user"] = user
        return attrs


class VerificationStatusSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)

    class Meta:
        model = TelegramVerification
        fields = ("id", "phone", "purpose", "status", "expires_at")
        read_only_fields = fields


class PasswordResetRequestSerializer(serializers.Serializer):
    """Parolni tiklashni boshlash: faqat telefon raqam."""

    phone = PhoneField(max_length=20)

    def validate_phone(self, phone):
        user = User.objects.filter(phone=phone, is_phone_verified=True).first()
        if user is None:
            raise serializers.ValidationError(
                "Bu raqam bilan ro'yxatdan o'tilmagan."
            )
        self.context["user"] = user
        return phone


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Kod va yangi parol."""

    verification_id = serializers.UUIDField()
    code = serializers.CharField(min_length=4, max_length=8)
    password = serializers.CharField(write_only=True, min_length=6, max_length=128)
    password2 = serializers.CharField(write_only=True, required=False)

    def validate(self, attrs):
        p2 = attrs.pop("password2", None)
        if p2 is not None and p2 != attrs.get("password"):
            raise serializers.ValidationError({"password2": "Parollar mos kelmadi."})
        return attrs
