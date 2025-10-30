from django.contrib import admin
from django.urls import path, include
from backend.apps.telegram_bot.webhook import telegram_webhook


def health_check(request):
    from django.http import JsonResponse

    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("webhook/telegram/", telegram_webhook, name="telegram-webhook"),
    path("healthz", health_check),
    path("sys_frontend/", include("backend.apps.sys_frontend.urls")), # include frontend URLs
]
