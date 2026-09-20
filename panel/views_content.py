"""Bannerlar, bildirishnomalar va sozlamalar."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.telegram import send_message
from core.models import ActivityLog, Banner, Notification, NotificationDelivery, SiteSetting

from .forms import BannerForm, NotificationForm, SiteSettingForm
from .utils import notify_deleted, notify_saved, paginate, staff_required


# ---------------------------------------------------------------- Bannerlar
@staff_required
def banner_list(request):
    qs = Banner.objects.order_by("order", "-created_at")
    return render(request, "panel/content/banners.html", {
        "page_title": _("Bannerlar"),
        "page": paginate(request, qs, 20),
    })


@staff_required
def banner_form(request, pk=None):
    obj = get_object_or_404(Banner, pk=pk) if pk else None
    form = BannerForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        notify_saved(request, form.save(), created=obj is None)
        return redirect("panel:banner_list")
    return render(request, "panel/content/banner_form.html", {
        "page_title": _("Banner qo'shish") if not obj else _("Bannerni tahrirlash"),
        "form": form, "obj": obj,
        "back_url": reverse("panel:banner_list"),
        "delete_url": reverse("panel:banner_delete", args=[obj.pk]) if obj else None,
    })


@staff_required
@require_POST
def banner_delete(request, pk):
    obj = get_object_or_404(Banner, pk=pk)
    notify_deleted(request, obj)
    obj.delete()
    return redirect("panel:banner_list")


@staff_required
@require_POST
def banner_toggle(request, pk):
    obj = get_object_or_404(Banner, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    messages.success(request, _("Banner yoqildi.") if obj.is_active else _("Banner o'chirildi."))
    return redirect("panel:banner_list")


# --------------------------------------------------------- Bildirishnomalar
@staff_required
def notification_list(request):
    qs = Notification.objects.select_related("course", "created_by").order_by("-created_at")
    return render(request, "panel/content/notifications.html", {
        "page_title": _("Bildirishnomalar"),
        "page": paginate(request, qs, 20),
    })


@staff_required
def notification_form(request, pk=None):
    obj = get_object_or_404(Notification, pk=pk) if pk else None
    if obj and obj.status == Notification.STATUS_SENT:
        messages.warning(request, _("Yuborilgan bildirishnomani tahrirlab bo'lmaydi."))
        return redirect("panel:notification_list")

    form = NotificationForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        notification = form.save(commit=False)
        if not notification.created_by_id:
            notification.created_by = request.user
        notification.save()
        form.save_m2m()
        notify_saved(request, notification, created=obj is None)

        if request.POST.get("action") == "send":
            return redirect("panel:notification_send", pk=notification.pk)
        return redirect("panel:notification_list")

    return render(request, "panel/content/notification_form.html", {
        "page_title": _("Bildirishnoma yaratish") if not obj else _("Bildirishnomani tahrirlash"),
        "form": form, "obj": obj,
    })


@staff_required
def notification_send(request, pk):
    """Bildirishnomani tanlangan auditoriyaga yuboradi."""
    notification = get_object_or_404(Notification, pk=pk)
    recipients = notification.audience_queryset()

    if request.method != "POST":
        return render(request, "panel/content/notification_send.html", {
            "page_title": _("Yuborish"),
            "obj": notification,
            "count": recipients.count(),
        })

    if notification.status == Notification.STATUS_SENT:
        messages.warning(request, _("Bu bildirishnoma allaqachon yuborilgan."))
        return redirect("panel:notification_list")

    deliveries = [
        NotificationDelivery(notification=notification, user=user)
        for user in recipients.only("id")
    ]
    NotificationDelivery.objects.bulk_create(deliveries, ignore_conflicts=True, batch_size=500)

    telegram_sent = 0
    if notification.send_telegram:
        text = f"<b>{notification.title}</b>\n\n{notification.body}"
        for user in recipients.exclude(telegram_id=None).only("id", "telegram_id"):
            if send_message(user.telegram_id, text):
                telegram_sent += 1

    notification.status = Notification.STATUS_SENT
    notification.sent_at = timezone.now()
    notification.recipients_count = len(deliveries)
    notification.save(update_fields=["status", "sent_at", "recipients_count"])
    ActivityLog.write(request.user, ActivityLog.ACTION_UPDATE, notification, _("Yuborildi"))

    messages.success(
        request,
        _("Bildirishnoma %(count)d ta foydalanuvchiga yuborildi.") % {"count": len(deliveries)}
        + (f" Telegram: {telegram_sent}." if notification.send_telegram else ""),
    )
    return redirect("panel:notification_list")


@staff_required
@require_POST
def notification_delete(request, pk):
    obj = get_object_or_404(Notification, pk=pk)
    notify_deleted(request, obj)
    obj.delete()
    return redirect("panel:notification_list")


# ---------------------------------------------------------------- Sozlamalar
@staff_required
def settings_view(request):
    from core.services import telegram_files

    obj = SiteSetting.get()
    form = SiteSettingForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        notify_saved(request, form.save())
        return redirect("panel:settings")

    return render(request, "panel/settings.html", {
        "page_title": _("Sozlamalar"),
        "form": form,
        "telegram_ready": telegram_files.is_configured(),
        "local_api": telegram_files.is_local_api(),
        "download_limit_mb": telegram_files.download_limit() // 1048576,
    })


@staff_required
def activity_log(request):
    qs = ActivityLog.objects.select_related("user")
    return render(request, "panel/activity.html", {
        "page_title": _("Amallar jurnali"),
        "page": paginate(request, qs, 40),
    })
