from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Consent
from backend.apps.users.models import Notification


@receiver(post_save, sender=Consent, dispatch_uid="consent_state_changed")
def consent_state_changed(sender, instance: Consent, **kwargs):
    if instance.status in {"revoked", "expired"}:
        # disable scheduled syncs, revoke tokens, inform user
        Notification.objects.create(
            user=instance.user,
            kind="consent_revoked",
            payload={"status": instance.status},
        )
        # tasks.stop_account_syncs.delay(instance.user_id)
        # tasks.revoke_oauth.delay(instance.user_id)
