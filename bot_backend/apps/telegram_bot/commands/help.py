from bot_backend.apps.telegram_bot.commands.base import BaseCommand


class HelpCommand(BaseCommand):
    def __init__(self):
        super().__init__(name="help", description="Show help information")

    def handle(self, message) -> None:
        help_text = (
            "Available commands:\n"
            "/start - Start interaction with the bot\n"
            "/help - Show this help message\n"
            "/status - Get current status\n"
            "/settings - Configure your settings\n"
        )
        # Here you would send the help_text back to the user via Telegram API
        print(f"Sending help message to chat_id {message.chat_id}:\n{help_text}")

    @staticmethod
    def task(message_data: dict) -> None:
        # This would be the Celery task implementation
        print(f"Processing help command for message data: {message_data}")
