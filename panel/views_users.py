"""Foydalanuvchilar bo'limi."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from billing.models import Subscription
from courses.models import Enrollment

from .forms import UserForm
from .utils import notify_deleted, notify_saved, paginate, staff_required

User = get_user_model()


@staff_required
def user_list(request):
    qs = User.objects.all().order_by("-date_joined")

    search = (request.GET.get("q") or "").strip()
    role = request.GET.get("role") or ""
    status = request.GET.get("status") or ""

    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) | Q(phone__icontains=search)
            | Q(school__icontains=search) | Q(region__icontains=search)
        )
    if role:
        qs = qs.filter(role=role)
    if status == "premium":
        qs = qs.filter(subscriptions__status=Subscription.STATUS_ACTIVE).distinct()
    elif status == "free":
        qs = qs.exclude(subscriptions__status=Subscription.STATUS_ACTIVE).distinct()
    elif status == "blocked":
        qs = qs.filter(is_blocked=True)
    elif status == "unverified":
        qs = qs.filter(is_phone_verified=False)

    qs = qs.annotate(courses_count=Count("enrollments", distinct=True))

    context = {
        "page_title": _("Foydalanuvchilar"),
        "page": paginate(request, qs),
        "search": search,
        "role": role,
        "status": status,
        "roles": User.ROLE_CHOICES,
        "total": qs.count(),
    }
    return render(request, "panel/users/list.html", context)


@staff_required
def user_detail(request, pk):
    user = get_object_or_404(User, pk=pk)
    enrollments = (
        Enrollment.objects.filter(user=user)
        .select_related("course")
        .order_by("-created_at")
    )
    context = {
        "page_title": user.full_name,
        "obj": user,
        "enrollments": enrollments,
        "subscriptions": user.subscriptions.select_related("plan").order_by("-created_at"),
        "payments": user.payments.order_by("-created_at")[:10],
        "orders": user.orders.order_by("-created_at")[:10],
    }
    return render(request, "panel/users/detail.html", context)


@staff_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, request.FILES or None, instance=user)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        notify_saved(request, obj)
        return redirect("panel:user_detail", pk=obj.pk)
    return render(request, "panel/users/form.html", {
        "page_title": _("Foydalanuvchini tahrirlash"),
        "form": form,
        "obj": user,
        "back_url": reverse("panel:user_detail", args=[user.pk]),
    })


@staff_required
@require_POST
def user_toggle_block(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, _("Superadminni bloklab bo'lmaydi."))
        return redirect("panel:user_detail", pk=pk)

    user.is_blocked = not user.is_blocked
    user.is_active = not user.is_blocked
    user.blocked_reason = request.POST.get("reason", "")[:200] if user.is_blocked else ""
    user.save(update_fields=["is_blocked", "is_active", "blocked_reason"])
    messages.success(request, _("Foydalanuvchi bloklandi.") if user.is_blocked
                     else _("Blokdan chiqarildi."))
    return redirect(request.META.get("HTTP_REFERER") or "panel:user_list")


@staff_required
@require_POST
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.is_superuser:
        messages.error(request, _("Superadminni o'chirib bo'lmaydi."))
        return redirect("panel:user_list")
    if user.pk == request.user.pk:
        messages.error(request, _("O'zingizni o'chira olmaysiz."))
        return redirect("panel:user_list")
    notify_deleted(request, user)
    user.delete()
    return redirect("panel:user_list")


@staff_required
def admin_list(request):
    """Administratorlar ro'yxati."""
    qs = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True) | Q(role=User.ROLE_ADMIN))
    return render(request, "panel/admins/list.html", {
        "page_title": _("Adminlar"),
        "page": paginate(request, qs.order_by("-is_superuser", "full_name")),
    })


@staff_required
def admin_form(request, pk=None):
    from .forms import AdminUserForm

    obj = get_object_or_404(User, pk=pk) if pk else None
    form = AdminUserForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        created = obj is None
        admin = form.save()
        notify_saved(request, admin, created=created)
        return redirect("panel:admin_list")
    return render(request, "panel/admins/form.html", {
        "page_title": _("Admin qo'shish") if not obj else _("Adminni tahrirlash"),
        "form": form,
        "obj": obj,
        "back_url": reverse("panel:admin_list"),
        "delete_url": reverse("panel:admin_delete", args=[obj.pk]) if obj else None,
    })


@staff_required
@require_POST
def admin_delete(request, pk):
    obj = get_object_or_404(User, pk=pk)
    if obj.is_superuser or obj.pk == request.user.pk:
        messages.error(request, _("Bu adminni o'chirib bo'lmaydi."))
        return redirect("panel:admin_list")
    obj.is_staff = False
    obj.role = User.ROLE_STUDENT
    obj.save(update_fields=["is_staff", "role"])
    messages.success(request, _("Admin huquqlari olib tashlandi."))
    return redirect("panel:admin_list")
