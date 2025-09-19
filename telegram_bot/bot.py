import os
from typing import Dict, Optional

import requests

from .commands import COMMAND_HANDLERS, CommandHandler
from .messages import TelegramMessage

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_ROOT = os.environ.get("TELEGRAM_API_ROOT", "https://api.telegram.org")
API_URL = f"{API_ROOT}/bot{TOKEN}"


class TelegramBot:
    """Core bot logic - simple and synchronous for clarity."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or TOKEN
        self.api_url = f"{API_ROOT}/bot{self.token}"
        self._handlers: Dict[str, CommandHandler] = {}
        print(f"🤖 Bot initialized with API: {self.api_url[:50]}...")
        self._register_default_commands()

    def _register_default_commands(self) -> None:
        for name, handler in COMMAND_HANDLERS.items():
            self.register_command(name, handler)

    def register_command(self, name: str, handler: CommandHandler) -> None:
        self._handlers[name] = handler

    def send_message(self, chat_id: int, text: str, parse_mode: Optional[str] = None) -> bool:
        """Send a message via Telegram Bot API - simple and sync."""
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
            print(f"✅ Message sent to {chat_id}: {text[:50]}...")
            return True
        except requests.RequestException as exc:
            print(f"❌ Error sending message to {chat_id}: {exc}")
            return False

    def handle_message(self, msg: TelegramMessage) -> None:
        """Route message to appropriate handler - simple sync dispatch."""
        print(f"🛠️ Processing command: {msg.command} from user {msg.user_id}")
        handler = self._handlers.get(msg.command or "")

        if not handler:
            self.send_message(msg.chat_id, "Unknown command. Try /help for available commands.")
            return

        try:
            handler(self, msg)
            print(f"✅ Command {msg.command} completed successfully")
        except Exception as exc:  # noqa: BLE001 - we want to surface all errors to the chat
            print(f"❌ Error processing command {msg.command}: {exc}")
            self.send_message(msg.chat_id, f"❌ Sorry, something went wrong: {exc}")


# Global bot instance
bot = TelegramBot()
