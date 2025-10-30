from django.contrib import admin
from .models import AffordabilitySnapshot



@admin.register(AffordabilitySnapshot)
class AffordabilitySnapshotAdmin(admin.ModelAdmin):
    list_display = ("user", "limit", "apr", "score_tier", "credit_score", "credit_factors", "combined_score", "calculated_at")
    list_filter = ("score_tier",)
    search_fields = ("user__username",)
    date_hierarchy = "calculated_at"
