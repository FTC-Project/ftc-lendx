from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import TokenEvent, CreditTrustBalance


@receiver(post_save, sender=TokenEvent, dispatch_uid="ctt_apply_event_to_balance")
def ctt_apply_event_to_balance(sender, instance: TokenEvent, created, **kwargs):
    if not created:
        return
    delta = instance.amount if instance.kind == "mint" else -instance.amount

    def _update():
        bal, _ = CreditTrustBalance.objects.select_for_update().get_or_create(
            user=instance.user
        )
        bal.balance = (bal.balance or 0) + delta
        bal.save(update_fields=["balance", "updated_at"])

    transaction.on_commit(_update)
