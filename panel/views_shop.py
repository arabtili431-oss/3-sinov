"""Do'kon bo'limi: mahsulotlar, kategoriyalar, buyurtmalar."""
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from shop.models import Order, Product, ProductCategory

from .forms import OrderStatusForm, ProductCategoryForm, ProductForm
from .utils import notify_deleted, notify_saved, paginate, staff_required


@staff_required
def product_list(request):
    qs = Product.objects.select_related("category")
    search = (request.GET.get("q") or "").strip()
    category = request.GET.get("category") or ""
    stock = request.GET.get("stock") or ""

    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
    if category:
        qs = qs.filter(category_id=category)
    if stock == "out":
        qs = qs.filter(stock__lte=0)
    elif stock == "low":
        qs = qs.filter(stock__gt=0, stock__lte=5)

    return render(request, "panel/shop/products.html", {
        "page_title": _("Mahsulotlar"),
        "page": paginate(request, qs.order_by("order", "-created_at")),
        "categories": ProductCategory.objects.all(),
        "search": search, "category": category, "stock": stock,
    })


@staff_required
def product_form(request, pk=None):
    obj = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        notify_saved(request, form.save(), created=obj is None)
        return redirect("panel:product_list")
    return render(request, "panel/shop/product_form.html", {
        "page_title": _("Mahsulot qo'shish") if not obj else _("Mahsulotni tahrirlash"),
        "form": form, "obj": obj,
        "back_url": reverse("panel:product_list"),
        "delete_url": reverse("panel:product_delete", args=[obj.pk]) if obj else None,
    })


@staff_required
@require_POST
def product_delete(request, pk):
    obj = get_object_or_404(Product, pk=pk)
    notify_deleted(request, obj)
    obj.delete()
    return redirect("panel:product_list")


@staff_required
@require_POST
def product_toggle(request, pk):
    obj = get_object_or_404(Product, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    messages.success(request, _("Sotuvga qo'yildi.") if obj.is_active else _("Sotuvdan olindi."))
    return redirect(request.META.get("HTTP_REFERER") or "panel:product_list")


@staff_required
def shop_category_list(request):
    qs = ProductCategory.objects.annotate(products_total=Count("products")).order_by("order", "name")
    return render(request, "panel/shop/categories.html", {
        "page_title": _("Do'kon kategoriyalari"),
        "page": paginate(request, qs, 30),
    })


@staff_required
def shop_category_form(request, pk=None):
    obj = get_object_or_404(ProductCategory, pk=pk) if pk else None
    form = ProductCategoryForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        notify_saved(request, form.save(), created=obj is None)
        return redirect("panel:shop_category_list")
    return render(request, "panel/shop/category_form.html", {
        "page_title": _("Kategoriya qo'shish") if not obj else _("Kategoriyani tahrirlash"),
        "form": form, "obj": obj,
        "back_url": reverse("panel:shop_category_list"),
        "delete_url": reverse("panel:shop_category_delete", args=[obj.pk]) if obj else None,
    })


@staff_required
@require_POST
def shop_category_delete(request, pk):
    obj = get_object_or_404(ProductCategory, pk=pk)
    notify_deleted(request, obj)
    obj.delete()
    return redirect("panel:shop_category_list")


@staff_required
def order_list(request):
    qs = Order.objects.select_related("user").prefetch_related("items")
    search = (request.GET.get("q") or "").strip()
    status = request.GET.get("status") or ""
    if search:
        qs = qs.filter(Q(number__icontains=search) | Q(full_name__icontains=search)
                       | Q(phone__icontains=search))
    if status:
        qs = qs.filter(status=status)

    totals = Order.objects.aggregate(
        paid=Sum("total", filter=Q(status__in=[Order.STATUS_PAID, Order.STATUS_SHIPPED, Order.STATUS_DONE])),
    )
    return render(request, "panel/shop/orders.html", {
        "page_title": _("Buyurtmalar"),
        "page": paginate(request, qs.order_by("-created_at")),
        "statuses": Order.STATUS_CHOICES,
        "search": search, "status": status,
        "revenue": totals["paid"] or 0,
        "new_count": Order.objects.filter(status=Order.STATUS_NEW).count(),
    })


@staff_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("user").prefetch_related("items__product"), pk=pk)
    form = OrderStatusForm(request.POST or None, instance=order)
    if request.method == "POST" and form.is_valid():
        previous = Order.objects.get(pk=order.pk).status
        obj = form.save()
        if previous != obj.status and obj.status == Order.STATUS_PAID:
            obj.mark_paid()
        notify_saved(request, obj)
        return redirect("panel:order_detail", pk=obj.pk)
    return render(request, "panel/shop/order_detail.html", {
        "page_title": _("Buyurtma") + f" {order.number}",
        "order": order, "form": form,
    })


@staff_required
@require_POST
def order_delete(request, pk):
    obj = get_object_or_404(Order, pk=pk)
    notify_deleted(request, obj)
    obj.delete()
    return redirect("panel:order_list")
