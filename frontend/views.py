"""Sahifalarni ko'rsatuvchi oddiy view'lar (API'ni fetch orqali chaqiradi)."""
from django.conf import settings
from django.shortcuts import render


def _ctx():
    return {"bot_username": (settings.TELEGRAM_BOT_USERNAME or "").lstrip("@")}


def login_page(request):
    return render(request, "auth/login.html", _ctx())


def register_page(request):
    return render(request, "auth/register.html", _ctx())


def verify_page(request):
    return render(request, "auth/verify.html", _ctx())


def password_reset_page(request):
    return render(request, "auth/password_reset.html", _ctx())


def dashboard_page(request):
    """Eski 'kabinet' havolasi — endi Asosiy sahifaga yo'naltiradi."""
    return render(request, "site/home.html", _ctx())


# --------------------------------------------------------------- Ommaviy sayt
def home_page(request):
    return render(request, "site/home.html", _ctx())


def shop_page(request):
    return render(request, "site/shop.html", _ctx())


def product_detail_page(request, slug):
    return render(request, "site/product_detail.html", {**_ctx(), "slug": slug})


def cart_page(request):
    return render(request, "site/cart.html", _ctx())


def courses_page(request):
    return render(request, "site/courses.html", _ctx())


def course_detail_page(request, slug):
    return render(request, "site/course_detail.html", {**_ctx(), "slug": slug})


def lesson_page(request, slug, lesson_id):
    return render(request, "site/lesson.html", {**_ctx(), "slug": slug, "lesson_id": lesson_id})


def leaderboard_page(request):
    return render(request, "site/leaderboard.html", _ctx())


def premium_page(request):
    return render(request, "site/premium.html", _ctx())


def miniapp_page(request):
    return render(request, "site/miniapp.html", _ctx())
