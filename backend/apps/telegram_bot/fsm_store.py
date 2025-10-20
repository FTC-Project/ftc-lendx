# backend/apps/telegram_bot/fsm_store.py
import json
import time
from typing import Optional, Dict, Any
from contextlib import contextmanager
from redis import Redis
from django.conf import settings

KEY = "tg:fsm:v1:{chat_id}"
LOCK = "tg:fsm:lock:{chat_id}"
TTL = 15 * 60  # 15 minutes


class FSMStore:
    def __init__(self, r: Optional[Redis] = None):
        self.r = r or Redis.from_url(
            getattr(settings, "CELERY_BROKER_URL", "redis://redis:6379/0")
        )

    def get(self, chat_id: int) -> Optional[Dict[str, Any]]:
        raw = self.r.get(KEY.format(chat_id=chat_id))
        return json.loads(raw) if raw else None

    def set(self, chat_id: int, command: str, step: str, data: Dict[str, Any]):
        payload = {
            "chat_id": chat_id,
            "command": command,  # e.g., "send"
            "step": step,  # e.g., "wait_recipient"
            "data": data or {},
            "ts": int(time.time()),
        }
        self.r.setex(KEY.format(chat_id=chat_id), TTL, json.dumps(payload))

    def clear(self, chat_id: int):
        self.r.delete(KEY.format(chat_id=chat_id))

    @contextmanager
    def lock(self, chat_id: int, ttl: int = 3):
        token = str(time.time())
        ok = self.r.set(LOCK.format(chat_id=chat_id), token, nx=True, ex=ttl)
        try:
            yield bool(ok)
        finally:
            cur = self.r.get(LOCK.format(chat_id=chat_id))
            if cur and cur.decode() == token:
                self.r.delete(LOCK.format(chat_id=chat_id))
