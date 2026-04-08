from django.db import models

from apps.core.models import TenantAwareModel, TimeStampedModel


class GoogleCalendarConfig(TenantAwareModel, TimeStampedModel):
    nome = models.CharField(max_length=150)
    client_id = models.CharField(max_length=500)
    client_secret = models.CharField(max_length=500)
    calendar_id = models.CharField(
        max_length=300,
        default="primary",
        help_text='ID da agenda do Google. Use "primary" para a agenda principal.',
    )
    refresh_token = models.TextField(blank=True)
    conectada = models.BooleanField(default=False)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Configuracao Google Calendar"
        verbose_name_plural = "Configuracoes Google Calendar"
        unique_together = [["tenant", "nome"]]

    def __str__(self):
        return self.nome
