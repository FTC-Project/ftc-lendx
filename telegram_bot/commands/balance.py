from typing import TYPE_CHECKING

from bot_backend.apps.users.models import TelegramUser, Wallet
from bot_backend.apps.users.xrpl_service import get_balance

from ..messages import TelegramMessage
from .utils import user_exists

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Check user's XRP balance."""
    try:
        if not user_exists(msg.user_id):
            bot.send_message(msg.chat_id, "❌ Please use /start first to create your account.")
            return

        user = TelegramUser.objects.get(telegram_id=msg.user_id)
        if not hasattr(user, "wallet"):
            bot.send_message(msg.chat_id, "❌ You don't have a wallet yet. Use /wallet to create one.")
            return

        wallet_address = Wallet.objects.get(user=user).address
        balance = get_balance(wallet_address)

        if balance is None:
            bot.send_message(msg.chat_id, "❌ Could not retrieve balance. Please try again later.")
            return

        bot.send_message(msg.chat_id, f"💰 Your balance: {balance} XRP")
    except TelegramUser.DoesNotExist:
        bot.send_message(msg.chat_id, "❌ Please use /start first to create your account.")
    except Exception as exc:
        print(f"Error in balance command: {exc}")
        bot.send_message(msg.chat_id, "❌ Could not retrieve balance. Please try again later.")
