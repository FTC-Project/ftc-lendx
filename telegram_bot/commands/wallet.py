from typing import TYPE_CHECKING

from bot_backend.apps.users.crypto import encrypt_secret
from bot_backend.apps.users.models import TelegramUser, Wallet
from bot_backend.apps.users.xrpl_service import create_user_wallet

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Create a new XRPL wallet for the user."""
    try:
        user = TelegramUser.objects.get(telegram_id=msg.user_id)
        if hasattr(user, "wallet"):
            bot.send_message(msg.chat_id, "❌ You already have a wallet.")
            return

        gen_wallet = create_user_wallet()
        Wallet.objects.create(
            user=user,
            network="testnet",
            address=gen_wallet.classic_address,
            secret_encrypted=encrypt_secret(gen_wallet.seed),
        )
        print(f"🔍 Created wallet for user {user.telegram_id}: {gen_wallet.classic_address}")
        bot.send_message(
            msg.chat_id,
            f"🆕 Wallet created!\nAddress: {gen_wallet.classic_address}\nYou have been credited with test XRP.\nUse /balance to check your balance.",
        )
    except TelegramUser.DoesNotExist:
        bot.send_message(msg.chat_id, "❌ Please use /start first to create your account.")
    except Exception as exc:
        print(f"❌ Error in wallet command: {exc}")
        bot.send_message(msg.chat_id, "❌ Could not create wallet. Please try again later.")
