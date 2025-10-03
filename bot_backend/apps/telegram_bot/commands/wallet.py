from celery import shared_task
from bot_backend.apps.telegram_bot.commands.base import BaseCommand
from bot_backend.apps.telegram_bot.messages import TelegramMessage
from bot_backend.apps.telegram_bot.tasks import send_telegram_message_task
from bot_backend.apps.users.crypto import encrypt_secret
from bot_backend.apps.users.models import TelegramUser, Wallet
from bot_backend.apps.users.xrpl_service import create_user_wallet



class WalletCommand(BaseCommand):
    def __init__(self):
        super().__init__(name="wallet", description="Create a new XRPL wallet")

    def handle(self, message: TelegramMessage) -> None:
        send_telegram_message_task.delay(message.chat_id, "⏳ Creating your wallet...")
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        if not msg:
            print("Invalid message data in wallet command")
            return
        print(f"Processing /wallet for user {msg.user_id}")
        try:
            try:
                user = TelegramUser.objects.get(telegram_id=msg.user_id)
            except TelegramUser.DoesNotExist:
                send_telegram_message_task.delay(msg.chat_id, "❌ Please use /start first to create your account.")
                return

            if hasattr(user, "wallet"):
                send_telegram_message_task.delay(msg.chat_id, "❌ You already have a wallet.")
                return

            gen_wallet = create_user_wallet()
            Wallet.objects.create(
                user=user,
                network="testnet",
                address=gen_wallet.classic_address,
                secret_encrypted=encrypt_secret(gen_wallet.seed),
            )

            send_telegram_message_task.delay(
                msg.chat_id,
                (
                    "🆕 Wallet created!\n"
                    f"Address: {gen_wallet.classic_address}\n"
                    "You have been credited with test XRP.\n"
                    "Use /balance to check your balance."
                ),
            )
            print(f"Wallet created for user {user.telegram_id}: {gen_wallet.classic_address}")
        except Exception as exc:
            print(f"Error in wallet command: {exc}")
            send_telegram_message_task.delay(msg.chat_id, "❌ Could not create wallet. Please try again later.")
