from django.apps import AppConfig


class TokensConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backend.apps.tokens'
    verbose_name = 'Tokens'
    
    def ready(self):
        import backend.apps.tokens.signals  # noqa
