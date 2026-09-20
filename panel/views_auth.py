"""Panelga kirish/chiqish va interfeys sozlamalari."""
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.shortcuts import redirect, render, resolve_url
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import PanelLoginForm


def panel_login(request):
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect("panel:dashboard")

    form = PanelLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["phone"],
            password=form.cleaned_data["password"],
        )
        if user is None:
            messages.error(request, _("Telefon raqam yoki parol noto'g'ri."))
        elif not (user.is_staff or user.is_superuser or getattr(user, "is_admin_role", False)):
            messages.error(request, _("Sizda admin panelga kirish huquqi yo'q."))
        else:
            login(request, user)
            return redirect(request.GET.get("next") or resolve_url("panel:dashboard"))

    return render(request, "panel/login.html", {"form": form})


def panel_logout(request):
    logout(request)
    return redirect("panel:login")


@require_POST
def set_theme(request):
    """Tungi/yorug' rejimni cookie'ga yozadi."""
    theme = request.POST.get("theme", "light")
    theme = theme if theme in ("light", "dark") else "light"
    response = JsonResponse({"theme": theme})
    response.set_cookie("vector_theme", theme, max_age=31536000, samesite="Lax")
    return response


def set_language(request, code):
    """Panel tilini almashtiradi."""
    from core.i18n import LANGUAGE_CODES

    if code not in LANGUAGE_CODES:
        code = "uz"
    translation.activate(code)
    response = redirect(request.META.get("HTTP_REFERER") or "panel:dashboard")
    response.set_cookie("django_language", code, max_age=31536000, samesite="Lax")
    request.session["_language"] = code
    return response
