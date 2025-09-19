from typing import TYPE_CHECKING

from bot_backend.apps.users.models import TelegramUser

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Handle /start command - create user if needed."""
    print(f"🔍 START command for user {msg.user_id}")

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
        print(f"🔍 User {'created' if created else 'found'}: {user.telegram_id}")

        if created:
            welcome_text = f"🚀 Welcome to XRPL Bot, {msg.first_name or 'friend'}!\n\nI'll help you manage XRP on the XRPL TestNet.\n\nWe created your account. You can use /help to see available commands."
        else:
            welcome_text = f"🚀 Welcome back, {msg.first_name or 'friend'}!\n\nUse /help to see available commands."

        bot.send_message(msg.chat_id, welcome_text)
        print("🔍 START command completed")
    except Exception as exc:
        print(f"❌ Error in start command: {exc}")
        bot.send_message(msg.chat_id, "Sorry, something went wrong during setup!")
