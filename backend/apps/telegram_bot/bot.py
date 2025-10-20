import os
from typing import Dict, Optional

from functools import lru_cache

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.commands.balance import BalanceCommand
from backend.apps.telegram_bot.commands.help import HelpCommand
from backend.apps.telegram_bot.commands.prices import PricesCommand
from backend.apps.telegram_bot.commands.send import SendCommand
from backend.apps.telegram_bot.commands.start import StartCommand
from backend.apps.telegram_bot.commands.wallet import WalletCommand

from .messages import TelegramMessage





class TelegramBot:
    """Dispatch Telegram commands and talk to the Bot API."""
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
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


@lru_cache(maxsize=1)
def get_bot(token: Optional[str] = None) -> TelegramBot:
    """Return a singleton TelegramBot instance."""
    return TelegramBot(token)
