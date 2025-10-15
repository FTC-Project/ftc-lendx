import uuid
from django.db import models
from backend.apps.users.models import TelegramUser

class DataAccessLog(models.Model):
    """FR-8.1: every access to sensitive data (banking, KYC, tokens, loans)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(TelegramUser, on_delete=models.SET_NULL, null=True, related_name="data_access_logs")
    actor = models.CharField(max_length=64, db_index=True)  # system|admin|user|webhook
    resource = models.CharField(max_length=64, db_index=True)  # e.g., banking.transactions
    action = models.CharField(max_length=32, db_index=True)    # read|write|delete|export
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ErasureRequest(models.Model):
    """FR-8.4 user right to erasure requests."""
    STATUS = [("pending","Pending"),("processed","Processed"),("denied","Denied")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="erasure_requests")
    status = models.CharField(max_length=16, choices=STATUS, default="pending", db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
