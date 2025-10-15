# backend/scoring/models.py
import uuid
from django.db import models
from backend.apps.users.models import TelegramUser

class TrustScoreSnapshot(models.Model):
    """Immutable score history (FR-3.*)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="score_snapshots")
    trust_score = models.DecimalField(max_digits=5, decimal_places=2)  # 0–100
    risk_category = models.CharField(max_length=32, db_index=True)    # New/Good/Excellent/High Risk...
    factors = models.JSONField(default=dict, blank=True)  # pillar breakdown
    explanation = models.TextField(blank=True, default="")
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
