from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import TelegramVerification, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-date_joined",)
    list_display = ("phone", "full_name", "role", "region", "district", "grade", "is_phone_verified", "is_active")
    list_filter = ("role", "is_phone_verified", "is_active", "is_staff", "region")
    search_fields = ("phone", "full_name", "school", "telegram_username")
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Shaxsiy ma'lumotlar", {"fields": ("full_name", "birth_date", "region", "district", "school", "grade")}),
        ("Rol", {"fields": ("role", "subject")}),
        ("Telegram", {"fields": ("telegram_id", "telegram_username")}),
        ("Ruxsatlar", {"fields": ("is_phone_verified", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Sanalar", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone", "full_name", "role", "password1", "password2"),
        }),
    )


@admin.register(TelegramVerification)
class TelegramVerificationAdmin(admin.ModelAdmin):
    list_display = ("phone", "purpose", "status", "attempts", "created_at", "expires_at")
    list_filter = ("purpose", "is_used")
    search_fields = ("phone", "start_token")
    readonly_fields = ("id", "start_token", "code_hash", "created_at")
