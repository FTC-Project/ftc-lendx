from django.contrib import admin
from .models import TelegramUser, Wallet, BotSession, Notification


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = (
        "telegram_id",
        "username",
        "first_name",
        "last_name",
        "role",
        "is_active",
        "created_at",
    )
    search_fields = (
        "telegram_id",
        "username",
        "first_name",
        "last_name",
        "phone_e164",
        "national_id",
    )
    list_filter = ("role", "is_active")
    date_hierarchy = "created_at"


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "network", "address", "created_at")
    search_fields = ("address", "user__username")
    list_filter = ("network",)


@admin.register(BotSession)
class BotSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "state", "updated_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "sent", "created_at", "sent_at")
    list_filter = ("kind", "sent")
    search_fields = ("user__username",)
