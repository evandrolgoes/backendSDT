from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class AccountsPayable(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    STATUS_PENDING = "A pagar"
    STATUS_PAID = "Pago"
    EMPRESA_EVANDRO_PF = "Evandro PF"
    EMPRESA_FLAVIA_PF = "Flavia pF"
    EMPRESA_IMPERE = "Impere"
    EMPRESA_SDT = "SDT"
    EMPRESA_CHOICES = [
        (EMPRESA_EVANDRO_PF, "Evandro PF"),
        (EMPRESA_FLAVIA_PF, "Flavia pF"),
        (EMPRESA_IMPERE, "Impere"),
        (EMPRESA_SDT, "SDT"),
    ]
    CONTA_ITAU_PERSON_EVANDRO = "itau Person - Evandro"
    CONTA_ITAU_SDT = "Itau - SDT"
    CONTA_ORIGEM_CHOICES = [
        (CONTA_ITAU_PERSON_EVANDRO, "itau Person - Evandro"),
        (CONTA_ITAU_SDT, "Itau - SDT"),
    ]
    STATUS_CHOICES = [
        (STATUS_PENDING, "A pagar"),
        (STATUS_PAID, "Pago"),
    ]

    descricao = models.CharField(max_length=255, blank=True)
    data_pagamento = models.DateField(null=True, blank=True)
    data_vencimento = models.DateField(null=True, blank=True)
    empresa = models.CharField(max_length=150, choices=EMPRESA_CHOICES)
    conta_origem = models.CharField(max_length=150, choices=CONTA_ORIGEM_CHOICES, blank=True)
    obs = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    valor_total = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        ordering = ["data_vencimento", "-created_at"]
        verbose_name = "Conta a pagar"
        verbose_name_plural = "Contas a pagar"

    def __str__(self):
        return f"{self.empresa} - {self.descricao or self.id}"
