from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TelegramUser
from backend.apps.kyc.models import KYCVerification


# Make a KYC Verification Object with status pending when user object created
@receiver(
    post_save, sender=TelegramUser, dispatch_uid="users.signals.create_related_objects"
)
def create_related_objects(sender, instance, created, **kwargs):
    if created:
        # Create a KYC Verification Object
        KYCVerification.objects.create(user=instance, status="pending")


# Make a celery event fire when a notification is created for score update
@receiver(
    post_save, sender=TelegramUser, dispatch_uid="users.signals.notify_on_score_update"
)
def notify_on_score_update(sender, instance, created, **kwargs):
    if created:
        pass  # Placeholder for future implementation
