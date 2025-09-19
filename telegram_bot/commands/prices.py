from typing import TYPE_CHECKING

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Get XRP price data."""
    days = 30

    if msg.args:
        try:
            days = int(msg.args[0])
            days = max(1, min(days, 365))
        except ValueError:
            bot.send_message(msg.chat_id, "❌ Invalid number of days. Using default (30).")

    try:
        bot.send_message(
            msg.chat_id,
            f"📈 XRP prices for the last {days} days:\n[Price API integration coming soon]",
        )
    except Exception as exc:
        print(f"❌ Error in prices command: {exc}")
        bot.send_message(msg.chat_id, "❌ Could not fetch price data. Please try again later.")
