from django.apps import AppConfig
from django.conf import settings


class TelegramBotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.telegram_bot"
    verbose_name = "Telegram Bot"

    def ready(self):
        """
        Keep this for optional future hooks, like signal imports
        or automatic task registration (Celery autodiscovery).
        """
        from backend.apps.telegram_bot import commands  # noqa: F401
        from .bot import get_bot

        token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        get_bot(token)
