from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AffordabilitySnapshot
from backend.apps.users.models import Notification


@receiver(post_save, sender=AffordabilitySnapshot, dispatch_uid="score_notify_on_new")
def score_notify_on_new(sender, instance: AffordabilitySnapshot, created, **kwargs):
    if created:
        Notification.objects.create(
            user=instance.user,
            kind="score_updated",
            payload={
                "score": float(instance.combined_score),
                "tier": instance.score_tier,
                "limit": float(instance.limit),
            },
        )
