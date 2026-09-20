from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("payme/", views.payme_endpoint, name="payme"),
    path("click/", views.click_endpoint, name="click"),
    path("natija/", views.payment_result, name="result"),
]
