from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


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


class ClientAgendaEvent(TenantAwareModel, TimeStampedModel, CreatedByMixin):
    class RepeatChoices(models.TextChoices):
        NONE = "", "Nao repetir"
        WEEKLY = "weekly", "Semanal"
        MONTHLY = "monthly", "Mensal"

    titulo = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    local = models.CharField(max_length=255, blank=True)
    participantes = models.TextField(blank=True)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fim = models.TimeField(null=True, blank=True)
    dia_todo = models.BooleanField(default=False)
    repeticao = models.CharField(max_length=20, choices=RepeatChoices.choices, blank=True, default="")
    repetir_ate = models.DateField(null=True, blank=True)
    grupos = models.ManyToManyField(
        "clients.EconomicGroup",
        blank=True,
        related_name="client_agenda_events",
    )
    subgrupos = models.ManyToManyField(
        "clients.SubGroup",
        blank=True,
        related_name="client_agenda_events",
    )

    class Meta:
        ordering = ["data_inicio", "hora_inicio", "id"]
        indexes = [
            models.Index(fields=["tenant", "data_inicio"]),
            models.Index(fields=["tenant", "data_fim"]),
            models.Index(fields=["tenant", "repeticao"]),
        ]

    def __str__(self):
        return self.titulo
