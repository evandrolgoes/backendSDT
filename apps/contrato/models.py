from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel
from apps.receivables.models import EntryClient


class Contract(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    class ContractStatus(models.TextChoices):
        PENDING_SIGNATURE = "Pendente assinatura", "Pendente assinatura"
        PENDING_FORMALIZATION = "Pendente formalizacao", "Pendente formalizacao"
        SIGNED = "Assinado", "Assinado"

    cliente = models.ForeignKey(EntryClient, on_delete=models.PROTECT, related_name="contratos")
    frequencia_pagamentos = models.CharField(max_length=120)
    status_contrato = models.CharField(max_length=30, choices=ContractStatus.choices, default=ContractStatus.PENDING_SIGNATURE)
    produto = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=18, decimal_places=2)
    data_inicio_contrato = models.DateField()
    data_fim_contrato = models.DateField()
    valor_total_contrato = models.DecimalField(max_digits=18, decimal_places=2)
    descricao = models.TextField(blank=True)

    class Meta:
        ordering = ["-data_inicio_contrato", "-created_at"]
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"

    def __str__(self):
        return f"{self.cliente} - {self.produto}"
