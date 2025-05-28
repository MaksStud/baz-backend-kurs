from django.apps import AppConfig


class TechnicalSupportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'technical_support'

    def ready(self):
        """Link to signals file."""
        import technical_support.signals
