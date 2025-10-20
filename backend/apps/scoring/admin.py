from django.contrib import admin
from .models import TrustScoreSnapshot, RiskTier


@admin.register(TrustScoreSnapshot)
class TrustScoreSnapshotAdmin(admin.ModelAdmin):
    list_display = ("user", "trust_score", "risk_category", "calculated_at")
    list_filter = ("risk_category",)
    search_fields = ("user__username",)
    date_hierarchy = "calculated_at"


@admin.register(RiskTier)
class RiskTierAdmin(admin.ModelAdmin):
    list_display = ("name", "min_score", "max_score", "order")
    list_editable = ("min_score", "max_score", "order")
