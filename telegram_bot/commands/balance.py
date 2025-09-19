from typing import TYPE_CHECKING

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Queue balance lookup for async processing."""
    from ..tasks import balance_command_task

    bot.send_message(msg.chat_id, "⏳ Checking your balance...")
    balance_command_task.delay(msg.__dict__)
