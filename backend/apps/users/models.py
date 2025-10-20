# backend/users/models.py
import uuid
from django.db import models


class TelegramUser(models.Model):
    ROLE_CHOICES = [
        ("borrower", "Borrower"),
        ("admin", "Admin"),
        ("lender", "Lender"),
    ]
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    first_name = models.CharField(max_length=128, null=True, blank=True)
    last_name = models.CharField(max_length=128, null=True, blank=True)
    phone_e164 = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    national_id = models.CharField(
        max_length=32, null=True, blank=True, db_index=True
    )  # SA ID (mock)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="borrower")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def display_name(self):
        return (
            self.username
            or f"{self.first_name or ''} {self.last_name or ''}".strip()
            or str(self.telegram_id)
        )


class Wallet(models.Model):
    NETWORK_CHOICES = [("testnet", "TestNet"), ("mainnet", "MainNet")]
    user = models.OneToOneField(
        TelegramUser, on_delete=models.CASCADE, related_name="wallet"
    )
    network = models.CharField(
        max_length=16, choices=NETWORK_CHOICES, default="testnet"
    )
    address = models.CharField(max_length=64, unique=True)
    secret_encrypted = models.BinaryField()  # Fernet/AES
    funded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BotSession(models.Model):
    """Maintains conversation context across sessions (FR-7.6)."""

    user = models.OneToOneField(
        TelegramUser, on_delete=models.CASCADE, related_name="bot_session"
    )
    state = models.CharField(max_length=64, default="idle", db_index=True)
    context = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class Notification(models.Model):
    """Proactive loan/status notifications sent via Telegram (FR-7.4)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(
        max_length=32, db_index=True
    )  # e.g., loan_due, loan_approved
    payload = models.JSONField(default=dict, blank=True)
    sent = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "kind", "sent"])]
