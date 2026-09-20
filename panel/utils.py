"""Admin panel uchun yordamchi funksiyalar."""
from functools import wraps

from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, resolve_url
from django.utils.translation import gettext as _

PER_PAGE = 20


def staff_required(view=None, *, teachers_allowed=False):
    """Panelga faqat admin (yoki ruxsat berilgan o'qituvchi) kira oladi."""

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect(f"{resolve_url('panel:login')}?next={request.path}")
            allowed = user.is_staff or user.is_superuser or getattr(user, "is_admin_role", False)
            if not allowed and teachers_allowed and getattr(user, "is_teacher", False):
                allowed = True
            if not allowed:
                return HttpResponseForbidden(_("Sizda bu bo'limga ruxsat yo'q."))
            return func(request, *args, **kwargs)

        return wrapper

    return decorator(view) if view else decorator


def paginate(request, queryset, per_page=PER_PAGE):
    """Sahifalash — shablonlarda bir xil ishlatiladi."""
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page") or 1
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    return page


def querystring(request, **overrides):
    """Joriy GET parametrlarini saqlab, ba'zilarini almashtiradi."""
    params = request.GET.copy()
    for key, value in overrides.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()


def notify_saved(request, obj, created=False):
    from core.models import ActivityLog
    action = ActivityLog.ACTION_CREATE if created else ActivityLog.ACTION_UPDATE
    ActivityLog.write(request.user, action, obj)
    messages.success(request, _("Saqlandi.") if not created else _("Qo'shildi."))


def notify_deleted(request, obj):
    from core.models import ActivityLog
    ActivityLog.write(request.user, ActivityLog.ACTION_DELETE, obj)
    messages.success(request, _("O'chirildi."))


def money(value):
    """1234567 -> '1 234 567'"""
    try:
        return f"{float(value):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"
