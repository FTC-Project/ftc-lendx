from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import PoolDeposit, PoolWithdrawal, PoolAccount


@receiver(post_save, sender=PoolDeposit, dispatch_uid="pool_update_on_deposit")
def pool_update_on_deposit(sender, instance: PoolDeposit, created, **kwargs):
    """
    When a new deposit is created, increment the user's principal in PoolAccount.
    """
    if not created:
        return

    # Run inside an atomic transaction so select_for_update is valid
    with transaction.atomic():
        acc, _ = PoolAccount.objects.select_for_update().get_or_create(
            user=instance.user
        )
        acc.principal += instance.amount
        acc.save(update_fields=["principal", "updated_at"])


@receiver(post_save, sender=PoolWithdrawal, dispatch_uid="pool_update_on_withdrawal")
def pool_update_on_withdrawal(sender, instance: PoolWithdrawal, created, **kwargs):
    """
    When a withdrawal is created, decrement the user's principal/interest totals.
    """
    if not created:
        return

    with transaction.atomic():
        acc, _ = PoolAccount.objects.select_for_update().get_or_create(
            user=instance.user
        )
        acc.principal = max(0, acc.principal - instance.principal_out)
        acc.accrued_interest = max(0, acc.accrued_interest - instance.interest_out)
        acc.save(update_fields=["principal", "accrued_interest", "updated_at"])
