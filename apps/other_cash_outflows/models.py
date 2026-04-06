from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class OtherCashOutflow(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    class Status(models.TextChoices):
        PENDENTE = "Pendente", "Pendente"
        PAGO = "Pago", "Pago"

    grupo = models.ForeignKey("clients.EconomicGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="outras_saidas_caixa")
    subgrupo = models.ForeignKey("clients.SubGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="outras_saidas_caixa")
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    moeda = models.CharField(max_length=20, blank=True, default="R$")
    data_pagamento = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    obs = models.TextField(blank=True)

    class Meta:
        ordering = ["-data_pagamento", "-created_at"]
        verbose_name = "Outra saída Caixa"
        verbose_name_plural = "Outras saídas Caixa"
        indexes = [
            models.Index(fields=["tenant", "data_pagamento"]),
            models.Index(fields=["tenant", "moeda"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self):
        return self.descricao or f"Outra saída {self.pk}"
