from typing import TYPE_CHECKING

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Queue XRP transfer processing for asynchronous execution."""
    from ..tasks import send_command_task

    args = msg.args or []
    if len(args) < 2:
        bot.send_message(
            msg.chat_id,
            "Usage: /send @username amount\nExample: /send @alice 10.5",
        )
        return

    try:
        float(args[1])
    except ValueError:
        bot.send_message(msg.chat_id, "❌ Invalid amount. Please enter a valid number.")
        return

    bot.send_message(msg.chat_id, "⏳ Processing your transfer...")
    send_command_task.delay(msg.__dict__)
