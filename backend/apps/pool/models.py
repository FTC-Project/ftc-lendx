# backend/pool/models.py
import uuid
from django.db import models
from backend.apps.users.models import TelegramUser

class PoolAccount(models.Model):
    """Each depositor's principal/interest view (off-chain mirror of on-chain)."""
    user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name="pool_account")
    principal = models.BigIntegerField(default=0)  # wei-like minor unit if mirroring chain; POC: ZAR int
    accrued_interest = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

class PoolDeposit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="pool_deposits")
    amount = models.BigIntegerField()
    tx_hash = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

class PoolWithdrawal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="pool_withdrawals")
    principal_out = models.BigIntegerField()
    interest_out = models.BigIntegerField(default=0)
    tx_hash = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

class PoolSnapshot(models.Model):
    """Periodic snapshot (Celery beat) for reporting & reconciliation."""
    at = models.DateTimeField(primary_key=True)
    total_pool = models.BigIntegerField()
    total_principal = models.BigIntegerField()
    acc_interest_per_share = models.DecimalField(max_digits=30, decimal_places=18)
