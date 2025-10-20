# backend/loans/models.py
import uuid
from django.db import models
from backend.apps.users.models import TelegramUser


class Loan(models.Model):
    STATE = [
        ("created", "Created"),
        ("funded", "Funded"),
        ("disbursed", "Disbursed"),
        ("repaid", "Repaid"),
        ("defaulted", "Defaulted"),
        ("declined", "Declined"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="loans"
    )
    amount = (
        models.IntegerField()
    )  # cents or ZAR integer; choose one and be consistent; POC: ZAR integer
    term_days = models.PositiveIntegerField()
    apr_bps = models.PositiveIntegerField()  # 2500 = 25.00%
    state = models.CharField(
        max_length=16, choices=STATE, default="created", db_index=True
    )

    # Escrow/chain refs (XRPL EVM):
    contract_address = models.CharField(
        max_length=64, null=True, blank=True, db_index=True
    )
    escrow_address = models.CharField(
        max_length=64, null=True, blank=True, db_index=True
    )
    escrow_factory = models.CharField(max_length=64, null=True, blank=True)
    onchain_loan_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    # Disbursement/reconciliation
    disbursed_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    grace_days = models.PositiveIntegerField(default=7)

    # Denorm for fast lookups:
    repaid_amount = models.IntegerField(default=0)
    interest_portion = models.IntegerField(default=0)
    principal_portion = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "state", "created_at"])]


class LoanOffer(models.Model):
    """Offer presented to user prior to activation."""

    loan = models.OneToOneField(Loan, on_delete=models.CASCADE, related_name="offer")
    monthly_payment = models.IntegerField()  # ZAR
    total_repayable = models.IntegerField()  # ZAR
    breakdown = models.JSONField(default=dict)  # e.g., schedule preview
    created_at = models.DateTimeField(auto_now_add=True)


class RepaymentSchedule(models.Model):
    """Installment plan with expected dates/amounts (supports partials)."""

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="schedule")
    installment_no = models.PositiveIntegerField()
    due_at = models.DateTimeField(db_index=True)
    amount_due = models.IntegerField()  # ZAR
    amount_paid = models.IntegerField(default=0)
    status = models.CharField(
        max_length=16, default="pending", db_index=True
    )  # pending/partial/paid/late

    class Meta:
        unique_together = [("loan", "installment_no")]
        ordering = ["installment_no"]


class Repayment(models.Model):
    """Actual payments (supports partials, reversals)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="repayments")
    schedule = models.ForeignKey(
        RepaymentSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="repayments",
    )
    amount = models.IntegerField()  # ZAR
    received_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(
        max_length=32, default="telegram"
    )  # or bank_transfer, etc.
    tx_hash = models.CharField(
        max_length=128, null=True, blank=True, db_index=True
    )  # on-chain ref if used
    meta = models.JSONField(default=dict, blank=True)


class LoanEvent(models.Model):
    """Lifecycle audit (FR-8.2)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="events")
    name = models.CharField(
        max_length=32, db_index=True
    )  # created, funded, disbursed, repaid, defaulted, declined
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Disbursement(models.Model):
    """Outbound transfer to borrower (bank or chain)."""

    loan = models.OneToOneField(
        Loan, on_delete=models.CASCADE, related_name="disbursement"
    )
    destination = models.CharField(max_length=64)  # bank_account or chain address
    amount = models.IntegerField()
    status = models.CharField(
        max_length=16, default="pending", db_index=True
    )  # pending/sent/confirmed/failed
    tx_ref = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
