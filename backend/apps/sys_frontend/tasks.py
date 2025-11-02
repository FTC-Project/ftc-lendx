from __future__ import annotations

from celery import shared_task
from django.conf import settings

from backend.apps.pool.models import PoolDeposit
from backend.apps.tokens.services.ftc_token import FTCTokenService
from backend.apps.tokens.services.loan_system import LoanSystemService
from backend.apps.users.models import Notification, Wallet
from backend.apps.sys_frontend.deposit_status_store import DepositStatusStore


@shared_task(queue="scoring", bind=True, time_limit=120)
def process_deposit_ftct(self, wallet: str, private_key: str, amount: float, task_id: str = None) -> dict:
    """
    Approve and deposit FTCT into the pool and return before/after metrics.
    Runs on the scoring worker to offload web thread.
    Updates deposit status in Redis as it progresses.
    """
    task_id = task_id or self.request.id
    status_store = DepositStatusStore()
    
    try:
        # Initialize status tracking
        status_store.create(task_id, wallet, amount)
        
        ftc_service = FTCTokenService()
        loan_service = LoanSystemService()

        # Before metrics
        before_pool = float(loan_service.get_total_pool())
        before_shares = float(loan_service.get_total_shares())

        # Approve spending
        status_store.update_stage(task_id, "approving")
        approve_tx = ftc_service.approve(
            owner_address=wallet,
            spender_address=settings.LOANSYSTEM_ADDRESS,
            amount=amount,
            private_key=private_key,
        )
        
        approve_tx_hash = (
            approve_tx.get("tx_hash") if isinstance(approve_tx, dict) else str(approve_tx)
        )
        status_store.set_approve_tx(task_id, approve_tx_hash)

        # Deposit
        status_store.update_stage(task_id, "depositing")
        deposit_tx = loan_service.deposit_ftct(
            lender_address=wallet,
            amount=amount,
            lender_private_key=private_key,
        )
        
        deposit_tx_hash = (
            deposit_tx.get("tx_hash") if isinstance(deposit_tx, dict) else str(deposit_tx)
        )
        status_store.set_deposit_tx(task_id, deposit_tx_hash)

        # After metrics
        status_store.update_stage(task_id, "confirming")
        after_pool = float(loan_service.get_total_pool())
        after_shares = float(loan_service.get_total_shares())
        user_shares = float(loan_service.get_shares_of(wallet))
        user_value = (
            float(loan_service.get_share_value(user_shares)) if user_shares > 0 else 0.0
        )

        user = Wallet.objects.get(address=wallet).user
        PoolDeposit.objects.create(user=user, amount=amount, tx_hash=deposit_tx_hash)
        
        # Final result
        result = {
            "approve_tx_hash": approve_tx_hash,
            "deposit_tx_hash": deposit_tx_hash,
            "before_pool": before_pool,
            "before_shares": before_shares,
            "after_pool": after_pool,
            "after_shares": after_shares,
            "user_shares": user_shares,
            "user_value": user_value,
        }
        
        # Mark as successful in status store
        status_store.set_success(task_id, result)
        # Fire off a notification to the user that their deposit was successful.
        Notification.objects.create(
            user=user,
            kind="deposit_successful",
            payload={
                "amount": amount,
                "deposit_tx_hash": deposit_tx_hash,
                "approve_tx_hash": approve_tx_hash,
                "before_pool": before_pool,
                "before_shares": before_shares,
                "after_pool": after_pool,
                "after_shares": after_shares,
            },
        )
        return result
    
    except Exception as e:
        # Store error in status
        status_store.set_error(task_id, str(e))
        raise
