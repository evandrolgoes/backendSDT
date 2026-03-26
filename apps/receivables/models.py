from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class ReceiptEntry(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    cliente = models.CharField(max_length=255)
    data_recebimento = models.DateField(null=True, blank=True)
    data_vencimento = models.DateField(null=True, blank=True)
    nf = models.CharField(max_length=100, blank=True)
    observacoes = models.TextField(blank=True)
    produto = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=100, blank=True)
    valor = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-data_recebimento", "-created_at"]
        verbose_name = "Entrada recebimento"
        verbose_name_plural = "Entradas recebimentos"

    def __str__(self):
        return self.cliente or f"Entrada recebimento {self.pk}"
