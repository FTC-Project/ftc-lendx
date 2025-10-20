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
    """Parse incoming webhook data into clean message object."""
    message = data.get("message") or data.get("edited_message")
    if not message:
        return None

    user = message.get("from", {})
    chat = message.get("chat", {})
    text = (message.get("text") or "").strip()

    if not text or not text.startswith("/"):
        return None  # Only process commands for now

    return TelegramMessage(
        chat_id=chat["id"],
        user_id=user["id"],
        username=user.get("username"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
        text=text,
    )
