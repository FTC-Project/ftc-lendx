from celery import shared_task
from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register
from backend.apps.telegram_bot.tasks import send_telegram_message_task


@register(name="help", aliases=["/help"], description="Help/Information", permission="public")
class HelpCommand(BaseCommand):
    name = "help"
    description = "Help/Information"
    permission = "public"

    def handle(self, message: TelegramMessage) -> None:
        help_text = (
        "📋 Available Commands:\n\n"
        "/start - Get started with the bot\n"
        "/balance - Check your XRP balance\n"
        "/send @username amount - Send XRP to another user\n"
        "/prices [symbol] [days] - Get price history (default: XRP, 30 days)\n"
        "/prices [symbol] [start] [end] - Use a custom range (YYYY-MM-DD)\n"
        "/wallet - Create a new XRPL wallet\n"
        "/help - Show this help message\n\n"
        "Example: /send @alice 10.5"
    )
        send_telegram_message_task.delay(message.chat_id, help_text)
        

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        # Help doesn't need to use a worker since it's a flat response.
        pass
