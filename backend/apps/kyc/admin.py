from django.contrib import admin
from .models import Document, KYCVerification


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "kind", "mime_type", "created_at")
    list_filter = ("kind", "mime_type")
    search_fields = ("user__username",)


@admin.register(KYCVerification)
class KYCVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "confidence", "reviewed_at", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username",)
