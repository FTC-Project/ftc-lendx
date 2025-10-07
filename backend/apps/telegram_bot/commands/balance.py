from celery import shared_task
from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.tasks import send_telegram_message_task
from backend.apps.users.models import TelegramUser, Transfer, Wallet
from backend.apps.users.xrpl_service import get_balance



class BalanceCommand(BaseCommand):
    def __init__(self):
        super().__init__(name="balance", description="Check your XRP balance")

    def handle(self, message: TelegramMessage) -> None:
        send_telegram_message_task.delay(message.chat_id, "Checking your balance...")
        self.task.delay(self.serialize(message))
        

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        if not msg:
            print("Invalid message data in balance command")
            return
        print(f"Processing /balance for user {msg.user_id}")
        try:
            try:
                user = TelegramUser.objects.get(telegram_id=msg.user_id)
            except TelegramUser.DoesNotExist:
                send_telegram_message_task.delay(msg.chat_id, "❌ Please use /start first to create your account.")
                return

            if not hasattr(user, "wallet"):
                send_telegram_message_task.delay(msg.chat_id, "❌ You don't have a wallet yet. Use /wallet to create one.")
                return

            wallet_address = Wallet.objects.get(user=user).address
            balance = get_balance(wallet_address)

            if balance is None:
                send_telegram_message_task.delay(msg.chat_id, "❌ Could not retrieve balance. Please try again later.")
                return

            send_telegram_message_task.delay(msg.chat_id, f"💰 Your balance: {balance} XRP")

            # Send transaction history (last 5)
            recent_transfers = Transfer.objects.filter(
                sender=user,
            ).order_by("-created_at")[:5]
            if recent_transfers:
                history_lines = ["\n📝 Recent Transactions:"]
                for transfer in recent_transfers:
                    status_emoji = {
                        "pending": "⏳",
                        "validated": "✅",
                        "failed": "❌",
                    }.get(transfer.status, "")
                    amount_xrp = transfer.amount_drops / 1_000_000
                    recipient = f"@{transfer.recipient.username}" if transfer.recipient.username else "Unknown"
                    tx_line = f"{status_emoji} Sent {amount_xrp} XRP to {recipient}"
                    if transfer.tx_hash:
                        tx_line += f" (TX: {transfer.tx_hash})"
                    history_lines.append(tx_line)
                send_telegram_message_task.delay(msg.chat_id, "\n".join(history_lines))
            print(f"Balance response sent for user {msg.user_id}")
        except Exception as exc:
            print(f"Error in balance command: {exc}")
            send_telegram_message_task.delay(msg.chat_id, "❌ Could not retrieve balance. Please try again later.")


    