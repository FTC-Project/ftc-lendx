from typing import TYPE_CHECKING

from xrpl.utils import xrp_to_drops

from bot_backend.apps.users.crypto import decrypt_secret
from bot_backend.apps.users.models import TelegramUser, Transfer, Wallet
from bot_backend.apps.users.xrpl_service import get_balance, send_xrp

from ..messages import TelegramMessage
from .utils import user_exists

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Send XRP to another user."""
    if not user_exists(msg.user_id):
        bot.send_message(msg.chat_id, "❌ Please use /start first to create your account.")
        return

    if not msg.args or len(msg.args) < 2:
        bot.send_message(
            msg.chat_id,
            "Usage: /send @username amount\nExample: /send @alice 10.5",
        )
        return

    try:
        recipient_username = msg.args[0].lstrip("@")
        amount = float(msg.args[1])

        if recipient_username.lower() == (msg.username or "").lower():
            bot.send_message(msg.chat_id, "❌ You cannot send XRP to yourself.")
            return

        if not TelegramUser.objects.filter(username__iexact=recipient_username).exists():
            bot.send_message(msg.chat_id, f"❌ User @{recipient_username} not found.")
            return

        if amount <= 0:
            bot.send_message(msg.chat_id, "❌ Amount must be greater than 0")
            return

        sender = TelegramUser.objects.get(telegram_id=msg.user_id)
        if not hasattr(sender, "wallet"):
            bot.send_message(msg.chat_id, "❌ You don't have a wallet yet. Use /wallet to create one.")
            return

        sender_wallet = Wallet.objects.get(user=sender)
        sender_balance = get_balance(sender_wallet.address)

        if sender_balance is None or sender_balance < amount:
            bot.send_message(msg.chat_id, "❌ Insufficient balance.")
            return

        recipient = TelegramUser.objects.get(username__iexact=recipient_username)
        if not hasattr(recipient, "wallet"):
            bot.send_message(msg.chat_id, f"❌ User @{recipient_username} does not have a wallet yet.")
            return

        recipient_wallet = Wallet.objects.get(user=recipient)

        transfer = Transfer.objects.create(
            status="pending",
            sender=sender,
            recipient=recipient,
            destination_address=recipient_wallet.address,
            amount_drops=int(xrp_to_drops(amount)),
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
            bot.send_message(msg.chat_id, "❌ Transaction failed. Please try again later.")
            return

        transfer.tx_hash = tx_hash
        transfer.status = "validated"
        transfer.save()
        print(f"🔍 Sent {amount} XRP from {sender.telegram_id} to {recipient.telegram_id}, TX: {tx_hash}")

        bot.send_message(
            msg.chat_id,
            f"✅ Sent {amount} XRP to @{recipient_username}!\nTX Hash: {tx_hash}",
        )
    except ValueError:
        bot.send_message(msg.chat_id, "❌ Invalid amount. Please enter a valid number.")
    except TelegramUser.DoesNotExist:
        if "sender" not in locals():
            bot.send_message(msg.chat_id, "❌ Please use /start first to create your account.")
        else:
            bot.send_message(msg.chat_id, f"❌ User @{recipient_username} not found.")
    except Exception as exc:
        print(f"❌ Error in send command: {exc}")
        bot.send_message(msg.chat_id, f"❌ Failed to send XRP: {exc}")
