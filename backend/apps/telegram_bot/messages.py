from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass
class TelegramMessage:
    """Clean data structure for incoming messages."""

    chat_id: int
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    text: str
    callback_data: Optional[str] = None
    callback_query_id: str | None = None
    message_id: Optional[int] = None
    inline_message_id: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.text.startswith("/"):
            parts = self.text.split()
            self.command = parts[0][1:].lower()
            self.args = parts[1:] if len(parts) > 1 else []

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)

    # function to go from payload to TelegramMessage
    def from_payload(data: Dict[str, Any]) -> Optional["TelegramMessage"]:
        try:
            return TelegramMessage(**data)
        except TypeError:
            return None


def parse_telegram_message(data: Dict[str, Any]) -> Optional[TelegramMessage]:
    # --- Inline button clicks ---
    cq = data.get("callback_query")
    if cq:
        msg = cq.get("message") or {}
        chat = msg.get("chat") or {}
        user = cq.get("from") or {}
        return TelegramMessage(
            chat_id=chat.get("id"),
            user_id=user.get("id"),
            username=user.get("username"),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            text=(msg.get("text") or "").strip() or None,
            callback_data=cq.get("data"),  # e.g. "reg:back"
            callback_query_id=cq.get("id"),  # <-- the spinner stopper
            message_id=msg.get("message_id"),
            inline_message_id=cq.get("inline_message_id"),
        )

    # --- Normal messages / edited messages ---
    message = data.get("message") or data.get("edited_message")
    if message:
        user = message.get("from", {}) or {}
        chat = message.get("chat", {}) or {}
        text = (message.get("text") or "").strip()
        return TelegramMessage(
            chat_id=chat.get("id"),
            user_id=user.get("id"),
            username=user.get("username"),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            text=text if text else None,
            callback_data=None,
            callback_query_id=None,
        )

    print("[messages] Unsupported update type:", list(data.keys()))
    return None
