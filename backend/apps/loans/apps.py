from django.apps import AppConfig


class LoansConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backend.apps.loans'
    verbose_name = 'Loans'

    def ready(self):
        import backend.apps.loans.signals  # noqa
