from celery import shared_task
from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.tasks import send_telegram_message_task
from backend.apps.users.models import TelegramUser


class StartCommand(BaseCommand):
    def __init__(self):
        super().__init__(name="help", description="Show help information")

    def handle(self, message: TelegramMessage) -> None:
        send_telegram_message_task.delay(message.chat_id, "Setting up your account...")
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        # Help doesn't need to use a worker since it's a flat response.
        msg = TelegramMessage.from_payload(message_data)
        if not msg:
            print("Invalid message data in start command")
            return
        print(f"Processing /start for user {msg.user_id}")

        try:
            user, created = TelegramUser.objects.get_or_create(
                telegram_id=msg.user_id,
                defaults={
                    "username": msg.username,
                    "first_name": msg.first_name,
                    "last_name": msg.last_name,
                    "is_active": True,
                },
            )
            if created:
                welcome_text = (
                    f"🚀 Welcome to XRPL Bot, {msg.first_name or 'friend'}!\n\n"
                    "I'll help you manage XRP on the XRPL TestNet.\n\n"
                    "We created your account. You can use /help to see available commands."
                )
            else:
                welcome_text = (
                    f"🚀 Welcome back, {msg.first_name or 'friend'}!\n\n"
                    "Use /help to see available commands."
                )

            send_telegram_message_task.delay(msg.chat_id, welcome_text)
            print(f"START completed for user {user.telegram_id}")
        except Exception as exc:
            print(f"Error in start command: {exc}")
            send_telegram_message_task.delay(
                msg.chat_id, "Sorry, something went wrong during setup!"
            )
