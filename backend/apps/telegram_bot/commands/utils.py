from backend.apps.users.models import TelegramUser


def user_exists(telegram_id: int) -> bool:
    """Check if a Telegram user exists in the DB."""
    return TelegramUser.objects.filter(telegram_id=telegram_id).exists()
