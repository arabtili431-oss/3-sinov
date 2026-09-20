"""Premium tariflar, obunalar va to'lovlar."""
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from billing.models import Payment, Plan, PromoCode, Subscription

from .forms import GrantSubscriptionForm, PlanForm, PromoCodeForm
from .utils import notify_deleted, notify_saved, paginate, staff_required


@staff_required
def promo_code_list(request):
    qs = PromoCode.objects.all()
    return render(request, "panel/billing/promo_codes.html", {
        "page_title": _("Promo kodlar"),
        "page": paginate(request, qs, 30),
    })


@staff_required
def promo_code_form(request, pk=None):
    obj = get_object_or_404(PromoCode, pk=pk) if pk else None
    form = PromoCodeForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        notify_saved(request, form.save(), created=obj is None)
        return redirect("panel:promo_code_list")
    return render(request, "panel/billing/promo_code_form.html", {
        "page_title": _("Promo kod qo'shish") if not obj else _("Promo kodni tahrirlash"),
        "form": form, "obj": obj,
        "back_url": reverse("panel:promo_code_list"),
        "delete_url": reverse("panel:promo_code_delete", args=[obj.pk]) if obj else None,
    })


@staff_required
@require_POST
def promo_code_delete(request, pk):
    obj = get_object_or_404(PromoCode, pk=pk)
    notify_deleted(request, obj)
    obj.delete()
    return redirect("panel:promo_code_list")


@staff_required
@require_POST
def promo_code_toggle(request, pk):
    obj = get_object_or_404(PromoCode, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    messages.success(request, _("Kod yoqildi.") if obj.is_active else _("Kod o'chirildi."))
    return redirect("panel:promo_code_list")


@staff_required
def plan_list(request):
    qs = Plan.objects.annotate(subs=Count("subscriptions")).order_by("order", "price")
    return render(request, "panel/billing/plans.html", {
        "page_title": _("Premium tariflar"),
        "page": paginate(request, qs, 30),
    })


@staff_required
def plan_form(request, pk=None):
    obj = get_object_or_404(Plan, pk=pk) if pk else None
    form = PlanForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        notify_saved(request, form.save(), created=obj is None)
        return redirect("panel:plan_list")
    return render(request, "panel/billing/plan_form.html", {
        "page_title": _("Tarif qo'shish") if not obj else _("Tarifni tahrirlash"),
        "form": form, "obj": obj,
        "back_url": reverse("panel:plan_list"),
        "delete_url": reverse("panel:plan_delete", args=[obj.pk]) if obj else None,
    })


@staff_required
@require_POST
def plan_delete(request, pk):
    obj = get_object_or_404(Plan, pk=pk)
    notify_deleted(request, obj)
    obj.delete()
    return redirect("panel:plan_list")


@staff_required
@require_POST
def plan_toggle(request, pk):
    obj = get_object_or_404(Plan, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    messages.success(request, _("Tarif yoqildi.") if obj.is_active else _("Tarif o'chirildi."))
    return redirect("panel:plan_list")


@staff_required
def subscription_list(request):
    qs = Subscription.objects.select_related("user", "plan")
    status = request.GET.get("status") or ""
    search = (request.GET.get("q") or "").strip()
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(Q(user__full_name__icontains=search) | Q(user__phone__icontains=search))

    form = GrantSubscriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        sub = Subscription.objects.create(
            user=form.cleaned_data["user"],
            plan=form.cleaned_data["plan"],
            amount=0,
            granted_by=request.user,
        )
        sub.activate(days=form.cleaned_data["days"])
        messages.success(request, _("Premium obuna berildi."))
        return redirect("panel:subscription_list")

    return render(request, "panel/billing/subscriptions.html", {
        "page_title": _("Obunalar"),
        "page": paginate(request, qs.order_by("-created_at")),
        "statuses": Subscription.STATUS_CHOICES,
        "status": status, "search": search, "form": form,
        "active_count": Subscription.objects.filter(status=Subscription.STATUS_ACTIVE).count(),
    })


@staff_required
@require_POST
def subscription_cancel(request, pk):
    sub = get_object_or_404(Subscription, pk=pk)
    sub.cancel()
    messages.success(request, _("Obuna bekor qilindi."))
    return redirect("panel:subscription_list")


@staff_required
def payment_list(request):
    qs = Payment.objects.select_related("user")
    provider = request.GET.get("provider") or ""
    state = request.GET.get("state") or ""
    search = (request.GET.get("q") or "").strip()
    if provider:
        qs = qs.filter(provider=provider)
    if state:
        qs = qs.filter(state=state)
    if search:
        qs = qs.filter(Q(reference__icontains=search) | Q(external_id__icontains=search)
                       | Q(user__full_name__icontains=search) | Q(user__phone__icontains=search))

    paid = Payment.objects.filter(state=Payment.STATE_PAID)
    return render(request, "panel/billing/payments.html", {
        "page_title": _("To'lovlar"),
        "page": paginate(request, qs.order_by("-created_at")),
        "providers": Payment.PROVIDER_CHOICES,
        "states": Payment.STATE_CHOICES,
        "provider": provider, "state": state, "search": search,
        "total_paid": paid.aggregate(s=Sum("amount"))["s"] or 0,
        "count_paid": paid.count(),
    })
