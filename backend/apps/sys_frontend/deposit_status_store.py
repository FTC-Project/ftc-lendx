"""
Redis-based store for tracking deposit transaction status.
Similar to FSMStore but for tracking on-chain transaction progress.
"""

import json
import time
from typing import Optional, Dict, Any
from redis import Redis
from django.conf import settings


KEY_PREFIX = "deposit:status:"
TTL = 30 * 60  # 30 minutes (longer than deposit completion time)


class DepositStatusStore:
    """Store for tracking deposit transaction status and blockchain confirmation."""

    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis = redis_client or Redis.from_url(
            getattr(settings, "CELERY_BROKER_URL", "redis://redis:6379/0")
        )

    def create(self, task_id: str, wallet: str, amount: float) -> None:
        """Initialize deposit status tracking."""
        key = f"{KEY_PREFIX}{task_id}"
        data = {
            "task_id": task_id,
            "wallet": wallet,
            "amount": amount,
            "status": "pending",
            "stage": "initializing",
            "approve_tx_hash": None,
            "approve_tx_status": None,
            "deposit_tx_hash": None,
            "deposit_tx_status": None,
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            "error": None,
        }
        self.redis.setex(key, TTL, json.dumps(data))

    def update_stage(self, task_id: str, stage: str, **kwargs) -> None:
        """Update deposit processing stage."""
        key = f"{KEY_PREFIX}{task_id}"
        raw = self.redis.get(key)
        if not raw:
            return

        data = json.loads(raw)
        data["stage"] = stage
        data["updated_at"] = int(time.time())
        data.update(kwargs)
        self.redis.setex(key, TTL, json.dumps(data))

    def set_approve_tx(self, task_id: str, tx_hash: str) -> None:
        """Record approve transaction hash."""
        self.update_stage(
            task_id,
            "approving",
            approve_tx_hash=tx_hash,
            approve_tx_status="pending",
        )

    def set_deposit_tx(self, task_id: str, tx_hash: str) -> None:
        """Record deposit transaction hash."""
        self.update_stage(
            task_id,
            "depositing",
            deposit_tx_hash=tx_hash,
            deposit_tx_status="pending",
        )

    def set_success(self, task_id: str, result: Dict[str, Any]) -> None:
        """Mark deposit as successful with final results."""
        key = f"{KEY_PREFIX}{task_id}"
        raw = self.redis.get(key)
        if not raw:
            return

        data = json.loads(raw)
        data.update(
            {
                "status": "success",
                "stage": "completed",
                "updated_at": int(time.time()),
                "approve_tx_status": "confirmed",
                "deposit_tx_status": "confirmed",
            }
        )
        # Merge in result data (tx hashes, metrics, etc.)
        data.update(result)
        self.redis.setex(key, TTL, json.dumps(data))

    def set_error(self, task_id: str, error: str) -> None:
        """Mark deposit as failed."""
        key = f"{KEY_PREFIX}{task_id}"
        raw = self.redis.get(key)
        if not raw:
            return

        data = json.loads(raw)
        data.update(
            {
                "status": "error",
                "error": error,
                "updated_at": int(time.time()),
            }
        )
        self.redis.setex(key, TTL, json.dumps(data))

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current deposit status."""
        key = f"{KEY_PREFIX}{task_id}"
        raw = self.redis.get(key)
        if not raw:
            return None

        data = json.loads(raw)

        # Check blockchain status for pending transactions
        if data.get("approve_tx_hash") and data.get("approve_tx_status") == "pending":
            data["approve_tx_status"] = self._check_tx_status(data["approve_tx_hash"])

        if data.get("deposit_tx_hash") and data.get("deposit_tx_status") == "pending":
            data["deposit_tx_status"] = self._check_tx_status(data["deposit_tx_hash"])

        return data

    def _check_tx_status(self, tx_hash: str) -> str:
        """
        Check if a transaction is confirmed on-chain.
        Returns 'pending', 'confirmed', or 'failed'.
        """
        try:
            from backend.apps.tokens.services.ftc_token import FTCTokenService

            service = FTCTokenService()

            receipt = service.web3.eth.get_transaction_receipt(tx_hash)
            if receipt:
                return "confirmed" if receipt["status"] == 1 else "failed"
            return "pending"
        except Exception:
            # Transaction not found or not yet mined
            return "pending"

    def delete(self, task_id: str) -> None:
        """Delete deposit status (cleanup)."""
        key = f"{KEY_PREFIX}{task_id}"
        self.redis.delete(key)
