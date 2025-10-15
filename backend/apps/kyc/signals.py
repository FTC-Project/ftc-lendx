from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import KYCVerification
from backend.apps.audit.models import DataAccessLog
from backend.apps.users.models import Notification

@receiver(pre_save, sender=KYCVerification, dispatch_uid="kyc_track_status_change")
def kyc_track_status_change(sender, instance: KYCVerification, **kwargs):
    if not instance.pk:
        instance._old_status = None
    else:
        old = KYCVerification.objects.get(pk=instance.pk)
        instance._old_status = old.status

@receiver(post_save, sender=KYCVerification, dispatch_uid="kyc_on_verified")
def kyc_on_verified(sender, instance: KYCVerification, **kwargs):
    if instance._old_status != "verified" and instance.status == "verified":
        DataAccessLog.objects.create(
            user=instance.user,
            actor="system",
            resource="kyc.verification",
            action="update",
            context={"new_status": "verified"},
        )
        Notification.objects.create(
            user=instance.user, kind="kyc_verified", payload={}
        )
        # Optionally: advance bot state or unlock /linkbank
