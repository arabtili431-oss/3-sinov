from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

# Admin panelga kirish sahifasiga izoh qo'shamiz (login o'rniga telefon raqam)
admin.site.login_template = "vector_admin_login.html"
admin.site.site_header = "VECTOR boshqaruv paneli"
admin.site.site_title = "VECTOR admin"
admin.site.index_title = "Boshqaruv"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("boshqaruv/", include("panel.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("api.urls")),
    path("tolov/", include("billing.urls")),
    path("", include("frontend.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
