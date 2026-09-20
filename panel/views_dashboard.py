"""Boshqaruv paneli va statistika."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _

from billing.models import Payment, Subscription
from courses.models import Course, Enrollment, Lesson
from shop.models import Order, Product
from core.models import ActivityLog

from .utils import staff_required

User = get_user_model()


def _series(queryset, days, date_field="created_at", value_field=None):
    """Oxirgi `days` kun uchun kunlik qiymatlar qatorini qaytaradi."""
    start = timezone.localdate() - timedelta(days=days - 1)
    rows = (
        queryset.filter(**{f"{date_field}__date__gte": start})
        .annotate(day=TruncDate(date_field))
        .values("day")
        .annotate(total=Sum(value_field) if value_field else Count("id"))
    )
    by_day = {r["day"]: float(r["total"] or 0) for r in rows}
    labels, values = [], []
    for i in range(days):
        day = start + timedelta(days=i)
        labels.append(day.strftime("%d.%m"))
        values.append(by_day.get(day, 0))
    return labels, values


@staff_required
def dashboard(request):
    today = timezone.localdate()
    month_ago = timezone.now() - timedelta(days=30)

    users = User.objects.filter(is_phone_verified=True)
    paid = Payment.objects.filter(state=Payment.STATE_PAID)

    total_revenue = paid.aggregate(s=Sum("amount"))["s"] or 0
    month_revenue = paid.filter(created_at__gte=month_ago).aggregate(s=Sum("amount"))["s"] or 0

    labels, user_values = _series(users, 30, "date_joined")
    _labels2, revenue_values = _series(paid, 30, "created_at", "amount")

    # Kurslar bo'yicha o'quvchilar (eng ommaboplari)
    top_courses = (
        Course.objects.annotate(students=Count("enrollments"))
        .order_by("-students")[:6]
    )

    stats = {
        "users_total": users.count(),
        "users_today": users.filter(last_login__date=today).count(),
        "users_new_today": users.filter(date_joined__date=today).count(),
        "courses_total": Course.objects.count(),
        "courses_active": Course.objects.filter(is_active=True).count(),
        "lessons_total": Lesson.objects.count(),
        "premium_total": Subscription.objects.filter(status=Subscription.STATUS_ACTIVE).count(),
        "products_total": Product.objects.filter(is_active=True).count(),
        "orders_today": Order.objects.filter(created_at__date=today).count(),
        "orders_new": Order.objects.filter(status=Order.STATUS_NEW).count(),
        "enrollments_total": Enrollment.objects.count(),
        "revenue_total": total_revenue,
        "revenue_month": month_revenue,
    }

    context = {
        "page_title": _("Boshqaruv paneli"),
        "stats": stats,
        "chart_labels": labels,
        "chart_users": user_values,
        "chart_revenue": revenue_values,
        "recent_users": users.order_by("-date_joined")[:8],
        "recent_orders": Order.objects.select_related("user").order_by("-created_at")[:6],
        "top_courses": top_courses,
        "top_courses_labels": [c.title[:14] for c in top_courses],
        "top_courses_values": [c.students for c in top_courses],
        "activity": ActivityLog.objects.select_related("user")[:8],
    }
    return render(request, "panel/dashboard.html", context)


@staff_required
def statistics(request):
    period = request.GET.get("period", "30")
    days = {"7": 7, "30": 30, "90": 90, "365": 365}.get(period, 30)

    users = User.objects.filter(is_phone_verified=True)
    paid = Payment.objects.filter(state=Payment.STATE_PAID)

    labels, user_values = _series(users, days, "date_joined")
    _l1, enroll_values = _series(Enrollment.objects.all(), days, "created_at")
    _l2, revenue_values = _series(paid, days, "created_at", "amount")
    _l3, order_values = _series(Order.objects.all(), days, "created_at")

    # Daromad manbalari
    by_target = paid.values("target_type").annotate(total=Sum("amount"))
    target_labels = {
        Payment.TARGET_SUBSCRIPTION: _("Premium obunalar"),
        Payment.TARGET_ORDER: _("Do'kon savdolari"),
        Payment.TARGET_COURSE: _("Kurslar"),
    }
    revenue_sources = [(target_labels.get(r["target_type"], r["target_type"]), float(r["total"] or 0))
                       for r in by_target]

    course_rows = (
        Course.objects.annotate(students=Count("enrollments"))
        .filter(students__gt=0).order_by("-students")[:10]
    )

    plans = (
        Subscription.objects.filter(status=Subscription.STATUS_ACTIVE)
        .values("plan_name").annotate(total=Count("id")).order_by("-total")
    )

    context = {
        "page_title": _("Statistika"),
        "period": period,
        "labels": labels,
        "user_values": user_values,
        "enroll_values": enroll_values,
        "revenue_values": revenue_values,
        "order_values": order_values,
        "revenue_sources_labels": [r[0] for r in revenue_sources],
        "revenue_sources_values": [r[1] for r in revenue_sources],
        "course_rows": course_rows,
        "course_labels": [c.title[:14] for c in course_rows],
        "course_values": [c.students for c in course_rows],
        "plan_labels": [p["plan_name"] or "—" for p in plans],
        "plan_values": [p["total"] for p in plans],
        "totals": {
            "users": users.count(),
            "enrollments": Enrollment.objects.count(),
            "premium": Subscription.objects.filter(status=Subscription.STATUS_ACTIVE).count(),
            "revenue": paid.aggregate(s=Sum("amount"))["s"] or 0,
            "orders": Order.objects.count(),
            "lessons": Lesson.objects.count(),
        },
    }
    return render(request, "panel/statistics.html", context)
