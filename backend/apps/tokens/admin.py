from django.contrib import admin
from .models import CreditTrustBalance, TokenEvent, TokenTierRule


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


@admin.register(TokenTierRule)
class TokenTierRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "min_balance",
        "max_balance",
        "max_loan_cap",
        "base_apr_bps",
        "order",
    )
    list_editable = (
        "min_balance",
        "max_balance",
        "max_loan_cap",
        "base_apr_bps",
        "order",
    )
