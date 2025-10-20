from django.apps import AppConfig


class KycConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.kyc"
    verbose_name = "KYC"

    def ready(self):
        import backend.apps.kyc.signals  # noqa
