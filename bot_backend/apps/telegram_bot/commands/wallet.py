from typing import TYPE_CHECKING

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Queue wallet creation for asynchronous processing."""
    from ..tasks import wallet_command_task

    bot.send_message(msg.chat_id, "⏳ Creating your wallet...")
    wallet_command_task.delay(msg.__dict__)
