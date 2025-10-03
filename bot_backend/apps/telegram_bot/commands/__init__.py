from typing import Callable, Dict, TYPE_CHECKING

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    pass

CommandHandler = Callable[["TelegramBot", TelegramMessage], None]

from . import balance, help as help_command, prices, send, start, wallet  # noqa: E402


COMMAND_HANDLERS: Dict[str, CommandHandler] = {
    "start": start.handle,
    "help": help_command.handle,
    "balance": balance.handle,
    "send": send.handle,
    "prices": prices.handle,
    "wallet": wallet.handle,
}

__all__ = ["COMMAND_HANDLERS", "CommandHandler"]
