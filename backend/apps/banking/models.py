# backend/banking/models.py
import uuid
from django.db import models
from backend.apps.users.models import TelegramUser


class Consent(models.Model):
    STATUS = [("active", "Active"), ("revoked", "Revoked"), ("expired", "Expired")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="consents"
    )
    permissions = models.JSONField(default=list, blank=True)
    granted_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(
        max_length=16, choices=STATUS, default="active", db_index=True
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)  # e.g., ABSA consent ref

    class Meta:
        indexes = [models.Index(fields=["user", "status"])]


class OAuthToken(models.Model):
    """Encrypted ABSA tokens (auth + refresh), rotated as needed (FR-2.5)."""

    user = models.OneToOneField(
        TelegramUser, on_delete=models.CASCADE, related_name="bank_oauth"
    )
    provider = models.CharField(max_length=32, default="absa", db_index=True)
    access_token_enc = models.BinaryField()  # ciphertext
    refresh_token_enc = models.BinaryField()
    scope = models.CharField(max_length=255, blank=True, default="")
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class BankAccount(models.Model):
    """Logical bank account reference in ABSA AIS."""

    user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="bank_accounts"
    )
    provider = models.CharField(max_length=32, default="absa")
    external_account_id_enc = models.BinaryField()  # encrypted ext id
    display_name = models.CharField(max_length=128, null=True, blank=True)
    currency = models.CharField(max_length=8, default="ZAR")
    last_balance = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "provider"])]


class BankTransaction(models.Model):
    """6-month transaction history for scoring (FR-2.2)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="transactions"
    )
    posted_at = models.DateTimeField(db_index=True)
    description = models.TextField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)  # + credit / - debit
    tx_type = models.CharField(max_length=16, db_index=True)  # credit/debit
    category = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["account", "posted_at"]),
            models.Index(fields=["category"]),
        ]
