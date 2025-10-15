# backend/tokens/models.py
import uuid
from django.db import models
from backend.apps.users.models import TelegramUser

class CreditTrustBalance(models.Model):
    """Current CTT balance (can go negative)."""
    user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name="ctt_balance")
    balance = models.IntegerField(default=0)  # integer tokens in 'units'; scaling logic in app
    updated_at = models.DateTimeField(auto_now=True)

class TokenEvent(models.Model):
    """Mint/Burn audit trail (FR-6.* & FR-8.*)."""
    KIND = [("mint", "Mint"), ("burn", "Burn"), ("init", "Initialize")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="ctt_events")
    kind = models.CharField(max_length=8, choices=KIND, db_index=True)
    amount = models.IntegerField()
    reason = models.CharField(max_length=64, blank=True, default="")  # e.g., loan_repaid, loan_defaulted
    tx_hash = models.CharField(max_length=128, null=True, blank=True, db_index=True)  # on-chain ref if used
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "kind", "created_at"])]

class TokenTierRule(models.Model):
    """Maps token tier → caps/APR (data-driven; evolves as economics shifts)."""
    name = models.CharField(max_length=32, unique=True)  # New, Good, Excellent, High Risk
    min_balance = models.IntegerField()  # inclusive
    max_balance = models.IntegerField()  # inclusive
    max_loan_cap = models.IntegerField()  # ZAR
    base_apr_bps = models.IntegerField()  # 1500 = 15%
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
