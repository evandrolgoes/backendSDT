from django.apps import AppConfig


class AuditingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.auditing"

    def ready(self):
        from . import signals  # noqa: F401
