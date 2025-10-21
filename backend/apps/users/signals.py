from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TelegramUser
from backend.apps.kyc.models import KYCVerification


# Make a KYC Verification Object with status pending when user object created
@receiver(post_save, sender=TelegramUser)
def create_related_objects(sender, instance, created, **kwargs):
    if created:
        # Create a KYC Verification Object
        KYCVerification.objects.create(user=instance, status='pending')
        