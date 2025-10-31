from __future__ import annotations

from celery import shared_task
from django.conf import settings

from backend.apps.pool.models import PoolDeposit
from backend.apps.tokens.services.ftc_token import FTCTokenService
from backend.apps.tokens.services.loan_system import LoanSystemService
from backend.apps.users.models import Wallet


@shared_task(queue="scoring", bind=True, time_limit=120)
def process_deposit_ftct(self, wallet: str, private_key: str, amount: float) -> dict:
    """
    Approve and deposit FTCT into the pool and return before/after metrics.
    Runs on the scoring worker to offload web thread.
    """
    ftc_service = FTCTokenService()
    loan_service = LoanSystemService()

    # Before metrics
    before_pool = float(loan_service.get_total_pool())
    before_shares = float(loan_service.get_total_shares())

    # Approve spending
    approve_tx = ftc_service.approve(
        owner_address=wallet,
        spender_address=settings.LOANSYSTEM_ADDRESS,
        amount=amount,
        private_key=private_key,
    )

    # Deposit
    deposit_tx = loan_service.deposit_ftct(
        lender_address=wallet,
        amount=amount,
        lender_private_key=private_key,
    )

    # After metrics
    after_pool = float(loan_service.get_total_pool())
    after_shares = float(loan_service.get_total_shares())
    user_shares = float(loan_service.get_shares_of(wallet))
    user_value = float(loan_service.get_share_value(user_shares)) if user_shares > 0 else 0.0
    

    # Only return JSON-serializable primitives
    approve_tx_hash = approve_tx.get("tx_hash") if isinstance(approve_tx, dict) else str(approve_tx)
    deposit_tx_hash = deposit_tx.get("tx_hash") if isinstance(deposit_tx, dict) else str(deposit_tx)


    user = Wallet.objects.get(address=wallet).user
    PoolDeposit.objects.create(user=user, amount=amount, tx_hash=deposit_tx_hash)
    return {
        "approve_tx_hash": approve_tx_hash,
        "deposit_tx_hash": deposit_tx_hash,
        "before_pool": before_pool,
        "before_shares": before_shares,
        "after_pool": after_pool,
        "after_shares": after_shares,
        "user_shares": user_shares,
        "user_value": user_value,
    }


