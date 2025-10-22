# backend/scoring/models.py
import uuid
from django.db import models
from backend.apps.users.models import TelegramUser


class TrustScoreSnapshot(models.Model):
    """Immutable score history (FR-3.*)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="score_snapshots"
    )
    trust_score = models.DecimalField(max_digits=5, decimal_places=2)  # 0–100
    risk_category = models.CharField(
        max_length=32, db_index=True
    )  # New/Good/Excellent/High Risk...
    factors = models.JSONField(default=dict, blank=True)  # pillar breakdown
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "calculated_at"])]


class RiskTier(models.Model):
    """Data-driven categorization thresholds."""

    name = models.CharField(max_length=32, unique=True)
    min_score = models.PositiveIntegerField()  # inclusive
    max_score = models.PositiveIntegerField()  # inclusive
    description = models.CharField(max_length=256, blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]


class AffordabilitySnapshot(models.Model):
    """Immutable affordability and limit history."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="affordability_snapshots"
    )
    limit = models.DecimalField(max_digits=10, decimal_places=2)  # calculated limit
    apr = models.DecimalField(max_digits=5, decimal_places=2)  # annual percentage rate
    token_tier = models.CharField(
        max_length=32, db_index=True
    )  # Excellent/Good/New/High Risk...
    trust_score_snapshot = models.ForeignKey(
        TrustScoreSnapshot,
        on_delete=models.CASCADE,
        related_name="affordability_snapshots",
    )
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "calculated_at"])]