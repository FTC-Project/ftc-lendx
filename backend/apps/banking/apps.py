from django.apps import AppConfig


class BankingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.banking"
    verbose_name = "Banking"

    def ready(self):
        import backend.apps.banking.signals  # noqa
