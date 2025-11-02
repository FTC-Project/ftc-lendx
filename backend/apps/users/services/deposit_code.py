"""
Service for managing one-time deposit codes in Redis.
These codes allow secure transfer of wallet address and private key
from Telegram bot to the web frontend.
"""
import json
import secrets
import time
from typing import Optional, Dict
from redis import Redis
from django.conf import settings


# Redis key prefix for deposit codes
CODE_KEY_PREFIX = "deposit:code:"
CODE_TTL = 15 * 60  # 15 minutes expiration


class DepositCodeService:
    """Service for managing one-time deposit codes."""

    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis = redis_client or Redis.from_url(
            getattr(settings, "CELERY_BROKER_URL", "redis://redis:6379/0")
        )

    def generate_code(self, wallet_address: str, private_key: str) -> str:
        """
        Generate a secure one-time code and store wallet data in Redis.
        Returns the code (hex string).
        """
        # Generate a secure random code (32 bytes = 64 hex chars)
        code = secrets.token_hex(32)
        key = f"{CODE_KEY_PREFIX}{code}"

        # Store wallet data as JSON
        data = {
            "wallet": wallet_address,
            "private_key": private_key,
            "created_at": int(time.time()),
        }

        # Store with expiration
        self.redis.setex(key, CODE_TTL, json.dumps(data))
        return code

    def get_and_delete(self, code: str) -> Optional[Dict[str, str]]:
        """
        Retrieve wallet data for a code and delete it (one-time use).
        Returns dict with 'wallet' and 'private_key' or None if invalid/expired.
        """
        key = f"{CODE_KEY_PREFIX}{code}"
        raw = self.redis.get(key)

        if not raw:
            return None

        try:
            data = json.loads(raw)
            # Delete immediately after retrieval (one-time use)
            self.redis.delete(key)
            return {
                "wallet": data.get("wallet"),
                "private_key": data.get("private_key"),
            }
        except (json.JSONDecodeError, KeyError):
            # Best effort cleanup if data is corrupted
            self.redis.delete(key)
            return None

    def get_without_delete(self, code: str) -> Optional[Dict[str, str]]:
        """
        Retrieve wallet data without deleting (for form prefill).
        Returns dict with 'wallet' and 'private_key' or None if invalid/expired.
        """
        key = f"{CODE_KEY_PREFIX}{code}"
        raw = self.redis.get(key)

        if not raw:
            return None

        try:
            data = json.loads(raw)
            return {
                "wallet": data.get("wallet"),
                "private_key": data.get("private_key"),
            }
        except (json.JSONDecodeError, KeyError):
            return None

