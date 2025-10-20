from django.contrib import admin
from .models import DataAccessLog, ErasureRequest


@admin.register(DataAccessLog)
class DataAccessLogAdmin(admin.ModelAdmin):
    list_display = ("user", "actor", "resource", "action", "created_at")
    list_filter = ("actor", "resource", "action")
    search_fields = ("user__username",)
    date_hierarchy = "created_at"


@admin.register(ErasureRequest)
class ErasureRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "created_at", "processed_at")
    list_filter = ("status",)
    date_hierarchy = "created_at"
