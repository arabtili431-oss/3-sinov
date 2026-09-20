"""Autentifikatsiya API view'lari."""
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import TelegramVerification, User
from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    ResendSerializer,
    UserSerializer,
    VerificationStatusSerializer,
    VerifySerializer,
)
from .telegram import bot_start_url, send_code
from .utils import mask_phone


def tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def check_verification(verification, code):
    """Kodni tekshiradi. Xato bo'lsa (Response, None), to'g'ri bo'lsa (None, verification) qaytaradi."""
    if verification is None:
        return Response({"detail": "Tasdiqlash sessiyasi topilmadi."}, status=404), None
    if verification.is_used:
        return Response({"detail": "Bu kod allaqachon ishlatilgan."}, status=400), None
    if verification.is_expired:
        return Response({"detail": "Kod muddati tugagan. Qaytadan so'rang."}, status=400), None
    if not verification.code_hash:
        return Response(
            {"detail": "Kod hali yuborilmagan. Avval botga telefon raqamingizni ulashing."},
            status=400,
        ), None
    if verification.attempts >= settings.OTP_MAX_ATTEMPTS:
        return Response({"detail": "Urinishlar soni tugadi. Yangi kod so'rang."}, status=429), None
    if not verification.check_code(code):
        qoldi = max(settings.OTP_MAX_ATTEMPTS - verification.attempts, 0)
        return Response({"detail": f"Kod noto'g'ri. Yana {qoldi} ta urinish qoldi."}, status=400), None
    return None, verification


class RegisterView(GenericAPIView):
    """1-qadam: ma'lumotlarni qabul qiladi va Telegram deep-link qaytaradi."""

    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    throttle_scope = "auth_register"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        verification = TelegramVerification.start(
            phone=user.phone,
            purpose=TelegramVerification.PURPOSE_REGISTER,
            user=user,
        )
        # Agar foydalanuvchi avval botga ulangan bo'lsa — kodni darhol yuboramiz.
        if user.telegram_id:
            code = verification.issue_code(chat_id=user.telegram_id)
            send_code(user.telegram_id, code, user.full_name, verification.purpose)

        return Response(
            {
                "verification_id": str(verification.id),
                "status": verification.status,
                "phone_masked": mask_phone(user.phone),
                "bot_url": bot_start_url(verification.start_token),
                "bot_username": settings.TELEGRAM_BOT_USERNAME,
                "expires_in": settings.OTP_TTL_SECONDS,
                "message": "Telegram botni oching va telefon raqamingizni ulashing.",
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyView(GenericAPIView):
    """2-qadam: Telegramdan kelgan kodni tekshiradi va JWT beradi."""

    permission_classes = [AllowAny]
    serializer_class = VerifySerializer
    throttle_scope = "auth_verify"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        verification = TelegramVerification.objects.filter(
            id=serializer.validated_data["verification_id"]
        ).select_related("user").first()

        error, verification = check_verification(verification, serializer.validated_data["code"])
        if error:
            return error

        user = verification.user
        if user is None:
            user = User.objects.filter(phone=verification.phone).first()
        if user is None:
            return Response({"detail": "Foydalanuvchi topilmadi."}, status=404)

        user.is_phone_verified = True
        user.is_active = True
        if verification.telegram_chat_id and not user.telegram_id:
            user.telegram_id = verification.telegram_chat_id
        user.save(update_fields=["is_phone_verified", "is_active", "telegram_id"])

        verification.is_used = True
        verification.save(update_fields=["is_used"])

        return Response({"user": UserSerializer(user).data, "tokens": tokens_for(user)})


class ResendCodeView(GenericAPIView):
    """Kodni qayta yuborish (bot bilan bog'langan bo'lsa)."""

    permission_classes = [AllowAny]
    serializer_class = ResendSerializer
    throttle_scope = "auth_resend"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = TelegramVerification.objects.filter(
            id=serializer.validated_data["verification_id"], is_used=False
        ).select_related("user").first()
        if verification is None:
            return Response({"detail": "Tasdiqlash sessiyasi topilmadi."}, status=404)
        if not verification.telegram_chat_id:
            return Response(
                {"detail": "Avval botga telefon raqamingizni ulashing.",
                 "bot_url": bot_start_url(verification.start_token)},
                status=400,
            )
        if verification.code_sent_at and (timezone.now() - verification.code_sent_at).total_seconds() < 60:
            return Response({"detail": "Yangi kodni 60 soniyadan keyin so'rang."}, status=429)

        code = verification.issue_code()
        name = verification.user.full_name if verification.user else ""
        send_code(verification.telegram_chat_id, code, name, verification.purpose)
        return Response({"status": verification.status, "expires_in": settings.OTP_TTL_SECONDS})


class VerificationStatusView(APIView):
    """Frontend polling: bot kodni yubordimi?"""

    permission_classes = [AllowAny]

    def get(self, request, pk):
        verification = TelegramVerification.objects.filter(id=pk).first()
        if verification is None:
            return Response({"detail": "Topilmadi."}, status=404)
        return Response(VerificationStatusSerializer(verification).data)


class LoginView(GenericAPIView):
    """Telefon + parol orqali kirish."""

    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    throttle_scope = "auth_login"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response({"user": UserSerializer(user).data, "tokens": tokens_for(user)})


class MeView(APIView):
    """Joriy foydalanuvchi ma'lumotlari."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class TelegramWebhookView(APIView):
    """Telegram webhook (polling o'rniga ishlatish mumkin)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, secret=None):
        from bot.handlers import handle_update

        if secret != settings.SECRET_KEY[:24]:
            return Response({"detail": "Ruxsat yo'q."}, status=403)
        handle_update(request.data or {})
        return Response({"ok": True})


class PasswordResetRequestView(GenericAPIView):
    """Parolni tiklashni boshlaydi: Telegramga kod yuboradi."""

    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer
    throttle_scope = "auth_reset"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.context["user"]

        verification = TelegramVerification.start(
            phone=user.phone,
            purpose=TelegramVerification.PURPOSE_RESET,
            user=user,
        )
        # Foydalanuvchi bot bilan allaqachon bog'langan — kodni darhol yuboramiz.
        if user.telegram_id:
            code = verification.issue_code(chat_id=user.telegram_id)
            send_code(user.telegram_id, code, user.full_name, verification.purpose)

        return Response({
            "verification_id": str(verification.id),
            "status": verification.status,
            "phone_masked": mask_phone(user.phone),
            "bot_url": bot_start_url(verification.start_token),
            "expires_in": settings.OTP_TTL_SECONDS,
        })


class PasswordResetConfirmView(GenericAPIView):
    """Kodni tekshiradi va yangi parolni o'rnatadi."""

    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer
    throttle_scope = "auth_verify"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        verification = TelegramVerification.objects.filter(
            id=serializer.validated_data["verification_id"],
            purpose=TelegramVerification.PURPOSE_RESET,
        ).select_related("user").first()

        error, verification = check_verification(verification, serializer.validated_data["code"])
        if error:
            return error

        user = verification.user or User.objects.filter(phone=verification.phone).first()
        if user is None:
            return Response({"detail": "Foydalanuvchi topilmadi."}, status=404)

        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])

        verification.is_used = True
        verification.save(update_fields=["is_used"])

        return Response({"user": UserSerializer(user).data, "tokens": tokens_for(user)})
