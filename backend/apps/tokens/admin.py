from django.contrib import admin
from .models import CreditTrustBalance, TokenEvent


@admin.register(CreditTrustBalance)
class CreditTrustBalanceAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    search_fields = ("user__username",)