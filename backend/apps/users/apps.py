from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backend.apps.users'

    def ready(self):
        import backend.apps.users.signals  # noqa
