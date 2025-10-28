from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from backend.apps.tokens.services.loan_system import LoanSystemService
from .models import Loan, Repayment, LoanEvent
from backend.apps.tokens.models import TokenEvent
from backend.apps.users.models import Notification
from django.utils import timezone


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
    if (
        loan.repaid_amount >= loan.amount + loan.interest_portion
        and loan.state == "disbursed"
    ):
        on_time = True
        if loan.due_date:
            past_due = (timezone.now() - loan.due_date).days
            on_time = past_due <= max(0, loan.grace_days)
        token_units = loan.amount // 100
        TokenEvent.objects.create(
            user=loan.user,
            kind=(
                "mint" if on_time else "mint_partial"
            ),  # half-credit could be handled in amount calc
            amount=token_units if on_time else max(1, token_units // 2),
            reason="loan_repaid_on_time" if on_time else "loan_repaid_late",
            meta={"loan_id": str(loan.id)},
        )


#NOTE: For testing:
BORROWER = {
    'address': '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC',
    'private_key': '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a',
}

# On create loan in our DB, create the loan on chain using the LoanSystemService
@receiver(post_save, sender=Loan, dispatch_uid="create_loan_on_chain")
def create_loan_on_chain(sender, instance: Loan, created, **kwargs):
    if not created:
        return
    loan = instance
    loan_system = LoanSystemService()
    loan_id, result = loan_system.create_loan(
        borrower_address=BORROWER['address'],
        amount=loan.amount,
        apr_bps=loan.apr_bps,
        term_days=loan.term_days,
    )
    loan.onchain_loan_id = loan_id
    Notification.objects.create(
        user=loan.user,
        kind="loan_created_on_chain",
        payload={"loan_id": loan_id, "amount": loan.amount, "apr_bps": loan.apr_bps, "term_days": loan.term_days},
    )
    loan_system.mark_funded(loan_id)
    # Now it's technically funded, another notification to the user
    Notification.objects.create(
        user=loan.user,
        kind="loan_funded_on_chain",
        payload={"loan_id": loan_id, "amount": loan.amount, "apr_bps": loan.apr_bps, "term_days": loan.term_days},
    )
    loan_system.mark_disbursed_ftct(loan_id)
    Notification.objects.create(
        user=loan.user,
        kind="loan_disbursed_on_chain",
        payload={"loan_id": loan_id, "amount": loan.amount, "apr_bps": loan.apr_bps, "term_days": loan.term_days},
    )
    # Update the state to Disbursed and store the onchain id
    loan.state = "disbursed"
    loan.onchain_loan_id = loan_id
    loan.save(update_fields=["state", "onchain_loan_id"])
