from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from .views import database_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/database-check/", database_check),
    path("api/", include("chat.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/payments/", include("payments.urls")),
    path("", lambda _: JsonResponse({"status": "ok"})),
]

# Serve media in dev
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
