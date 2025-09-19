from typing import TYPE_CHECKING

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Show available commands."""
    help_text = "📋 Available Commands:\n\n/start - Get started with the bot\n/balance - Check your XRP balance  \n/send @username amount - Send XRP to another user\n/prices [days] - Get XRP price data (default: 30 days)\n/wallet - Create a new XRPL wallet\n/help - Show this help message\n\nExample: /send @alice 10.5"
    bot.send_message(msg.chat_id, help_text)
