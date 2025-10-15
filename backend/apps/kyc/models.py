# backend/kyc/models.py
import uuid
from django.db import models
from backend.apps.users.models import TelegramUser

class Document(models.Model):
    """POC: store binary blobs in Postgres."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=32, db_index=True)  # id_front, id_back, selfie, proof_address
    blob = models.BinaryField()  # bytea
    mime_type = models.CharField(max_length=64, default="application/octet-stream")
    created_at = models.DateTimeField(auto_now_add=True)

class KYCVerification(models.Model):
    STATUS = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("failed", "Failed"),
    ]
    user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name="kyc")
    status = models.CharField(max_length=16, choices=STATUS, default="pending", db_index=True)
    confidence = models.FloatField(null=True, blank=True)
    result = models.JSONField(default=dict, blank=True)  # store mock checks
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
