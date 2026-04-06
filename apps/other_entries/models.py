from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class OtherEntry(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    class Status(models.TextChoices):
        RECEBIDO = "Recebido", "Recebido"
        PREVISTO = "Previsto", "Previsto"

    grupo = models.ForeignKey("clients.EconomicGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="outras_entradas")
    subgrupo = models.ForeignKey("clients.SubGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="outras_entradas")
    descricao = models.CharField(max_length=255)
    data_entrada = models.DateField(null=True, blank=True)
    valor = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    moeda = models.CharField(max_length=20, blank=True, default="R$")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PREVISTO)
    obs = models.TextField(blank=True)

    class Meta:
        ordering = ["-data_entrada", "-created_at"]
        verbose_name = "Outra entrada Caixa"
        verbose_name_plural = "Outras entradas Caixa"
        indexes = [
            models.Index(fields=["tenant", "data_entrada"]),
            models.Index(fields=["tenant", "moeda"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self):
        return self.descricao or f"Outra entrada {self.pk}"
