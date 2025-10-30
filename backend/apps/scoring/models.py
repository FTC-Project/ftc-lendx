# backend/scoring/models.py
import uuid
from django.db import models
from backend.apps.users.models import TelegramUser


class AffordabilitySnapshot(models.Model):
    """Limit, APR, Score Tier, Credit Score, Credit Factors, Combined Score"""

    SCORE_TIERS = [
        ("PLATINUM", "Platinum"),
        ("GOLD", "Gold"),
        ("SILVER", "Silver"),
        ("BRONZE", "Bronze"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="affordability_snapshots"
    )
    limit = models.DecimalField(max_digits=10, decimal_places=2)  # calculated limit
    apr = models.DecimalField(max_digits=5, decimal_places=2)  # annual percentage rate
    score_tier = models.CharField(
        max_length=10,
        choices=SCORE_TIERS,
        db_index=True,
        default="BRONZE",
    )
    credit_score = models.DecimalField(max_digits=5, decimal_places=2)  # 0–100
    credit_factors = models.JSONField(default=dict, blank=True)  # pillar breakdown
    token_score = models.DecimalField(max_digits=5, decimal_places=2)  # 0–100
    combined_score = models.DecimalField(max_digits=5, decimal_places=2)  # 0–100
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "calculated_at"])]
