from django.contrib import admin
from .models import (
    Loan,
    LoanOffer,
    RepaymentSchedule,
    Repayment,
    LoanEvent,
    Disbursement,
)


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "amount",
        "term_days",
        "apr_bps",
        "state",
        "disbursed_at",
        "due_date",
        "onchain_loan_id",
    )
    list_filter = ("state",)
    search_fields = (
        "id",
        "user__username",
        "contract_address",
        "escrow_address",
        "onchain_loan_id",
    )
    date_hierarchy = "created_at"


@admin.register(LoanOffer)
class LoanOfferAdmin(admin.ModelAdmin):
    list_display = ("loan", "monthly_payment", "total_repayable", "created_at")


@admin.register(RepaymentSchedule)
class RepaymentScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "loan",
        "installment_no",
        "due_at",
        "amount_due",
        "amount_paid",
        "status",
    )
    list_filter = ("status",)
    date_hierarchy = "due_at"


@admin.register(Repayment)
class RepaymentAdmin(admin.ModelAdmin):
    list_display = ("loan", "amount", "received_at", "method", "tx_hash")
    list_filter = ("method",)
    search_fields = ("tx_hash",)
    date_hierarchy = "received_at"


@admin.register(LoanEvent)
class LoanEventAdmin(admin.ModelAdmin):
    list_display = ("loan", "name", "created_at")
    list_filter = ("name",)
    date_hierarchy = "created_at"


@admin.register(Disbursement)
class DisbursementAdmin(admin.ModelAdmin):
    list_display = (
        "loan",
        "destination",
        "amount",
        "status",
        "tx_ref",
        "created_at",
        "confirmed_at",
    )
    list_filter = ("status",)
    search_fields = ("tx_ref",)
