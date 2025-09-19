import os
from typing import Dict, Optional

import requests

from .commands import COMMAND_HANDLERS, CommandHandler
from .messages import TelegramMessage

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_ROOT = os.environ.get("TELEGRAM_API_ROOT", "https://api.telegram.org")
API_URL = f"{API_ROOT}/bot{TOKEN}"


class TelegramBot:
    """Dispatch Telegram commands and talk to the Bot API."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or TOKEN
        self.api_url = f"{API_ROOT}/bot{self.token}"
        self._handlers: Dict[str, CommandHandler] = {}
        print(f"[bot] Initialized with API {self.api_url[:50]}...")
        self._register_default_commands()

    def _register_default_commands(self) -> None:
        for name, handler in COMMAND_HANDLERS.items():
            self.register_command(name, handler)

    def register_command(self, name: str, handler: CommandHandler) -> None:
        self._handlers[name] = handler

    def send_message(self, chat_id: int, text: str, parse_mode: Optional[str] = None) -> bool:
        """Send a message via the Telegram Bot API."""
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            print(f"[bot] Message sent to {chat_id}: {text[:50]}...")
            return True
        except requests.RequestException as exc:
            print(f"[bot] Error sending message to {chat_id}: {exc}")
            return False

    def handle_message(self, msg: TelegramMessage) -> None:
        """Schedule the matching command handler."""
        print(f"[bot] Dispatching command '{msg.command}' for user {msg.user_id}")
        handler = self._handlers.get(msg.command or "")

        if not handler:
            self.send_message(msg.chat_id, "Unknown command. Try /help for available commands.")
            return

        try:
            handler(self, msg)
            print(f"[bot] Handler queued for command '{msg.command}'")
        except Exception as exc:  # noqa: BLE001
            print(f"[bot] Error while scheduling {msg.command}: {exc}")
            self.send_message(msg.chat_id, f"❌ Sorry, something went wrong: {exc}")


# Global bot instance used across modules
bot = TelegramBot()
