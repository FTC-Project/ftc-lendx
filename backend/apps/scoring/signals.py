from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TrustScoreSnapshot
from backend.apps.users.models import Notification

@receiver(post_save, sender=TrustScoreSnapshot, dispatch_uid="score_notify_on_new")
def score_notify_on_new(sender, instance: TrustScoreSnapshot, created, **kwargs):
    if created:
        Notification.objects.create(
            user=instance.user, kind="score_updated",
            payload={"score": float(instance.trust_score), "risk": instance.risk_category}
        )
