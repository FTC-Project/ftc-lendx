from django.contrib import admin
from .models import CreditTrustBalance, TokenEvent


@admin.register(CreditTrustBalance)
class CreditTrustBalanceAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    search_fields = ("user__username",)


@admin.register(TokenEvent)
class TokenEventAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "amount", "reason", "tx_hash", "created_at")
    list_filter = ("kind",)
    search_fields = ("user__username", "tx_hash")
    date_hierarchy = "created_at"
