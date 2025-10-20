import json
import os
import random
import time
from typing import Optional, Dict, Any
from contextlib import contextmanager
from redis import Redis
from django.conf import settings

KEY = "tg:fsm:v1:{chat_id}"
LOCK = "tg:fsm:lock:{chat_id}"
TTL = 15 * 60  # 15 minutes

# atomic unlock (delete only if token matches the current value)
# returns 1 if deleted, 0 otherwise
_UNLOCK_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


class LockNotAcquired(RuntimeError):
    pass


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
            "command": command,
            "step": step,
            "data": data or {},
            "ts": int(time.time()),
        }
        self.r.setex(KEY.format(chat_id=chat_id), TTL, json.dumps(payload))

    def clear(self, chat_id: int):
        self.r.delete(KEY.format(chat_id=chat_id))

    @contextmanager
    def lock(
        self,
        chat_id: int,
        ttl: int = 3,
        *,
        retries: int = 6,
        backoff_base: float = 0.06,
        raise_on_fail: bool = True,
    ):
        """
        Acquire a per-chat lock with retries. If acquisition ultimately fails:
        - default: raise LockNotAcquired
        - if raise_on_fail=False, yield False (caller may branch explicitly)

        Exponential backoff with jitter to reduce contention.
        Uses a token and Lua script to release safely.
        """
        key = LOCK.format(chat_id=chat_id)
        token = f"{time.time()}:{os.getpid()}:{random.random()}"

        acquired = False
        attempt = 0
        while attempt <= retries:
            ok = self.r.set(key, token, nx=True, ex=ttl)
            if ok:
                acquired = True
                break
            # sleep with exp backoff + jitter
            sleep_s = backoff_base * (2**attempt) * (0.5 + random.random())
            time.sleep(sleep_s)
            attempt += 1

        if not acquired:
            if raise_on_fail:
                raise LockNotAcquired(f"Could not acquire lock for chat_id={chat_id}")
            # fall through to yield False explicitly if caller asked for it

        try:
            yield acquired
        finally:
            if acquired:
                try:
                    # only delete if token matches
                    self.r.eval(_UNLOCK_LUA, 1, key, token)
                except Exception:
                    # best-effort unlock; avoid crashing caller
                    pass

    # Atomic-ish data patch under the chat-scoped lock
    def update_data(self, chat_id: int, patch: Dict[str, Any]) -> None:
        """
        Merge `patch` into current state's `data` under the per-chat lock.
        Preserves command/step, refreshes TTL. No-op if state missing.
        """
        if not patch:
            return
        # Default behavior: raises if lock cannot be acquired
        with self.lock(chat_id):
            state = self.get(chat_id)
            if not state:
                return
            data = state.get("data") or {}
            if not isinstance(data, dict):
                data = {}
            data.update(patch)
            self.set(chat_id, state.get("command", ""), state.get("step", ""), data)
