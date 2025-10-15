from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Loan, Repayment, LoanEvent
from backend.apps.tokens.models import TokenEvent
from backend.apps.users.models import Notification
from django.utils import timezone

@receiver(pre_save, sender=Loan, dispatch_uid="loan_state_change_tracker")
def loan_state_change_tracker(sender, instance: Loan, **kwargs):
    if instance.pk:
        prev = Loan.objects.get(pk=instance.pk)
        instance._old_state = prev.state
    else:
        instance._old_state = None

@receiver(post_save, sender=Loan, dispatch_uid="loan_on_state_change")
def loan_on_state_change(sender, instance: Loan, **kwargs):
    if instance._old_state and instance._old_state != instance.state:
        LoanEvent.objects.create(loan=instance, name=instance.state, details={})
        Notification.objects.create(user=instance.user, kind=f"loan_{instance.state}", payload={"loan_id": str(instance.id)})

@receiver(post_save, sender=Repayment, dispatch_uid="repayment_reconcile")
def repayment_reconcile(sender, instance: Repayment, created, **kwargs):
    if not created:
        return
    loan = instance.loan
    # Update denorm
    loan.repaid_amount = (loan.repaid_amount or 0) + instance.amount
    # Mark schedule line items
    if instance.schedule:
        s = instance.schedule
        s.amount_paid += instance.amount
        s.status = "paid" if s.amount_paid >= s.amount_due else "partial"
        s.save(update_fields=["amount_paid", "status"])
    loan.save(update_fields=["repaid_amount"])

    # If fully repaid: emit token event (on-time vs late via due_date + grace_days)
    if loan.repaid_amount >= loan.amount + loan.interest_portion and loan.state == "disbursed":
        on_time = True
        if loan.due_date:
            past_due = (timezone.now() - loan.due_date).days
            on_time = past_due <= max(0, loan.grace_days)
        token_units = loan.amount // 100
        TokenEvent.objects.create(
            user=loan.user,
            kind="mint" if on_time else "mint",  # half-credit could be handled in amount calc
            amount=token_units if on_time else max(1, token_units // 2),
            reason="loan_repaid_on_time" if on_time else "loan_repaid_late",
            meta={"loan_id": str(loan.id)}
        )


