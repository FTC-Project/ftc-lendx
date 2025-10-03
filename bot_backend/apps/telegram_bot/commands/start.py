from typing import TYPE_CHECKING

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Schedule background processing for /start."""
    from ..tasks import start_command_task

    bot.send_message(msg.chat_id, "⏳ Setting up your account...")
    start_command_task.delay(msg.__dict__)
