from django.contrib import admin
from django.urls import path
from telegram_bot.webhook import telegram_webhook


def health_check(request):
    from django.http import JsonResponse
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("webhook/telegram/", telegram_webhook, name="telegram-webhook"),
    path("healthz",health_check),
]
