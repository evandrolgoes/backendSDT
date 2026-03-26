from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class AccountsPayable(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    data_pagamento = models.DateField(null=True, blank=True)
    data_vencimento = models.DateField(null=True, blank=True)
    empresa = models.CharField(max_length=150)
    forma_pagamento = models.CharField(max_length=100, blank=True)
    obs = models.TextField(blank=True)
    referencia = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=100, blank=True)
    valor_total = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        ordering = ["data_vencimento", "-created_at"]
        verbose_name = "Conta a pagar"
        verbose_name_plural = "Contas a pagar"

    def __str__(self):
        return f"{self.empresa} - {self.referencia or self.id}"
