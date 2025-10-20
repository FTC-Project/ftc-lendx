from celery import shared_task
from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.tasks import send_telegram_message_task
from backend.apps.users.crypto import decrypt_secret
from backend.apps.users.models import TelegramUser, Transfer, Wallet
from backend.apps.users.xrpl_service import get_balance, send_xrp
from xrpl.utils import xrp_to_drops


class SendCommand(BaseCommand):
    def __init__(self):
        super().__init__(
            name="send", description="Send cryptocurrency to another address"
        )

    def handle(self, message: TelegramMessage) -> None:
        send_telegram_message_task.delay(
            message.chat_id, "Processing your send request..."
        )
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        if not msg:
            print("Invalid message data in send command")
            return
        print(f"Processing /send from user {msg.user_id}")

        args = msg.args or []
        if len(args) < 2:
            send_telegram_message_task.delay(
                msg.chat_id,
                "Usage: /send @username amount\nExample: /send @alice 10.5",
            )
            return

        recipient_username = args[0].lstrip("@")

        try:
            amount = float(args[1])
        except ValueError:
            send_telegram_message_task.delay(
                msg.chat_id, "❌ Invalid amount. Please enter a valid number."
            )
            return

        if amount <= 0:
            send_telegram_message_task.delay(
                msg.chat_id, "❌ Amount must be greater than 0"
            )
            return

        try:
            if recipient_username.lower() == (msg.username or "").lower():
                send_telegram_message_task.delay(
                    msg.chat_id, "❌ You cannot send XRP to yourself."
                )
                return

            try:
                sender = TelegramUser.objects.get(telegram_id=msg.user_id)
            except TelegramUser.DoesNotExist:
                send_telegram_message_task.delay(
                    msg.chat_id, "❌ Please use /start first to create your account."
                )
                return

            if not hasattr(sender, "wallet"):
                send_telegram_message_task.delay(
                    msg.chat_id,
                    "❌ You don't have a wallet yet. Use /wallet to create one.",
                )
                return

            try:
                recipient = TelegramUser.objects.get(
                    username__iexact=recipient_username
                )
            except TelegramUser.DoesNotExist:
                send_telegram_message_task.delay(
                    msg.chat_id, f"❌ User @{recipient_username} not found."
                )
                return

            if not hasattr(recipient, "wallet"):
                send_telegram_message_task.delay(
                    msg.chat_id,
                    f"❌ User @{recipient_username} does not have a wallet yet.",
                )
                return

            sender_wallet = Wallet.objects.get(user=sender)
            recipient_wallet = Wallet.objects.get(user=recipient)

            sender_balance = get_balance(sender_wallet.address)
            if sender_balance is None or sender_balance < amount:
                send_telegram_message_task.delay(
                    msg.chat_id, "❌ Insufficient balance."
                )
                return

            transfer = Transfer.objects.create(
                status="pending",
                sender=sender,
                recipient=recipient,
                destination_address=recipient_wallet.address,
                amount_drops=int(xrp_to_drops(amount)),
            )
            send_telegram_message_task.delay(
                msg.chat_id, f"⏳ Sending {amount} XRP to @{recipient_username}..."
            )

            tx_hash = send_xrp(
                decrypt_secret(sender_wallet.secret_encrypted.tobytes()),
                recipient_wallet.address,
                amount,
            )

            if not tx_hash:
                transfer.tx_hash = None
                transfer.status = "failed"
                transfer.save()
                send_telegram_message_task.delay(
                    msg.chat_id, "❌ Transaction failed. Please try again later."
                )
                return

            transfer.tx_hash = tx_hash
            transfer.status = "validated"
            transfer.save()
            print(
                f"Sent {amount} XRP from {sender.telegram_id} to {recipient.telegram_id}, TX: {tx_hash}",
            )

            send_telegram_message_task.delay(
                msg.chat_id,
                f"✅ Sent {amount} XRP to @{recipient_username}!\nTX Hash: {tx_hash}",
            )
        except Exception as exc:
            print(f"Error in send command: {exc}")
            send_telegram_message_task.delay(
                msg.chat_id, f"❌ Failed to send XRP: {exc}"
            )
