from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Núcleo compartido de la API"

    def ready(self):
        # Registra la extensión de drf-spectacular para el token con expiración
        from . import schema  # noqa: F401
