"""To'lov tizimlaridan keladigan so'rovlar."""
import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import click as click_api
from . import payme as payme_api
from .models import Payment

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def payme_endpoint(request):
    """Payme Merchant API (JSON-RPC)."""
    try:
        payload = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": {"code": -32700, "message": "Parse error"}})

    result = payme_api.handle(request, payload)
    result["id"] = payload.get("id")
    return JsonResponse(result)


@csrf_exempt
@require_POST
def click_endpoint(request):
    """Click Prepare/Complete."""
    data = request.POST.dict() or json.loads(request.body.decode() or "{}")
    return JsonResponse(click_api.handle(data))


def payment_result(request):
    """Foydalanuvchi to'lovdan keyin qaytadigan sahifa."""
    reference = request.GET.get("reference") or request.GET.get("transaction_param", "")
    payment = Payment.objects.filter(reference=reference).first() if reference else None
    return render(request, "billing/result.html", {"payment": payment})
