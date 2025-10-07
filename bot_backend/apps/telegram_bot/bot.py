import os
from typing import Dict, Optional

import requests

from bot_backend.apps.telegram_bot.commands.base import BaseCommand
from bot_backend.apps.telegram_bot.commands.balance import BalanceCommand
from bot_backend.apps.telegram_bot.commands.help import HelpCommand
from bot_backend.apps.telegram_bot.commands.prices import PricesCommand
from bot_backend.apps.telegram_bot.commands.send import SendCommand
from bot_backend.apps.telegram_bot.commands.start import StartCommand
from bot_backend.apps.telegram_bot.commands.wallet import WalletCommand

from .messages import TelegramMessage

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_ROOT = os.environ.get("TELEGRAM_API_ROOT", "https://api.telegram.org")
API_URL = f"{API_ROOT}/bot{TOKEN}"



class TelegramBot:
    """Dispatch Telegram commands and talk to the Bot API."""
    def __init__(self, token: Optional[str] = None):
        self.token = token or TOKEN
        self.api_url = f"{API_ROOT}/bot{self.token}"
        print(f"[bot] Initialized with API {self.api_url[:50]}...") #convert to logger later TODO
        self.commands: Dict[str, BaseCommand] = {
        "help": HelpCommand(),
        "wallet": WalletCommand(),
        "prices": PricesCommand(),
        "balance": BalanceCommand(),
        "send": SendCommand(),
        "start": StartCommand(),
    }

    def dispatch_command(self, msg: TelegramMessage) -> None:
        command = self.commands.get(msg.command)
        if command:
            command.handle(msg)
        else:
            print(f"[bot] Unknown command '{msg.command}'")

    def handle_message(self, msg: TelegramMessage) -> None:
        """Schedule the matching command handler."""
        print(f"[bot] Dispatching command '{msg.command}' for user {msg.user_id}") # convert to logger later TODO
        try:
            self.dispatch_command(msg)
        except Exception as exc:  # Never crash the bot
            print(f"[bot] Error while scheduling {msg.command}: {exc}")
            # Just chill


# Global bot instance used across modules
bot = TelegramBot()
