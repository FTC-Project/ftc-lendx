from django.apps import AppConfig

class TelegramBotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.telegram_bot"
    verbose_name = "Telegram Bot"

    def ready(self):
        """
        Keep this for optional future hooks, like signal imports
        or automatic task registration (Celery autodiscovery).
        """
        # from . import signals  # Only if you ever create one
        pass
