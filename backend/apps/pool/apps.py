from django.apps import AppConfig


class PoolConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.pool"
    verbose_name = "Pool"

    def ready(self):
        import backend.apps.pool.signals  # noqa
