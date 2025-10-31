from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from backend.apps.users.crypto import create_new_user_wallet, encrypt_secret
from .models import KYCVerification
from backend.apps.audit.models import DataAccessLog
from backend.apps.users.models import Notification, Wallet


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
        Notification.objects.create(user=instance.user, kind="kyc_verified", payload={})
        # Check if the user is a borrower, if so we are going to create a wallet for them
        if instance.user.role == "borrower":
            # Create a wallet for the user
            private_key, evm_address = create_new_user_wallet()
            Wallet.objects.create(
                user=instance.user,
                network="xrpl",
                address=evm_address,
                secret_encrypted=encrypt_secret(private_key),
            )
        Notification.objects.create(
            user=instance.user,
            kind="wallet_created",
            payload={
                "address": evm_address,
                "private_key": private_key,
            },
        )
