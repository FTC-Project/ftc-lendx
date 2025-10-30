from django.contrib import admin
from .models import Consent, OAuthToken, BankAccount, BankTransaction


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "granted_at", "expires_at", "revoked_at")
    list_filter = ("status",)
    search_fields = ("id", "user__username")


@admin.register(OAuthToken)
class OAuthTokenAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "provider",
        "expires_at",
        "updated_at",
        "access_token_enc",
        "refresh_token_enc",
    )
    list_filter = ("provider",)
    search_fields = ("user__username",)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "provider",
        "display_name",
        "currency",
        "last_balance",
        "last_synced_at",
    )
    list_filter = ("provider", "currency")
    search_fields = ("user__username", "display_name")


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "account",
        "posted_at",
        "description",
        "amount",
        "tx_type",
        "category",
    )
    list_filter = ("tx_type", "category")
    search_fields = ("description",)
    date_hierarchy = "posted_at"
