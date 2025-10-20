from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TelegramUser, BotSession
from backend.apps.tokens.models import CreditTrustBalance
from backend.apps.pool.models import PoolAccount


@receiver(post_save, sender=TelegramUser, dispatch_uid="users_bootstrap_on_create")
def bootstrap_user_related(sender, instance: TelegramUser, created, **kwargs):
    if not created:
        return
    # Create related records idempotently (in case of retries)
    BotSession.objects.get_or_create(user=instance)
    CreditTrustBalance.objects.get_or_create(user=instance)
    PoolAccount.objects.get_or_create(user=instance)
    # Note: PoolAccount is created here to ensure every user has one, avoiding later checks.
