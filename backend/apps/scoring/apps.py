from django.apps import AppConfig


class ScoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.scoring"
    verbose_name = "Scoring"

    def ready(self):
        import backend.apps.scoring.signals  # noqa
