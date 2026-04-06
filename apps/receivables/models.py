from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class EntryClient(TenantAwareModel, TimeStampedModel):
    nome = models.CharField(max_length=255)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        constraints = [models.UniqueConstraint(fields=["tenant", "nome"], name="uq_entry_client_nome_tenant")]

    def __str__(self):
        return self.nome


class ReceiptEntry(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    class NfStatus(models.TextChoices):
        DESNECESSARIO = "Desnecessario", "Desnecessario"
        FEITO_ENVIADO = "Feito e enviado", "Feito e enviado"
        PENDENTE = "Pendente", "Pendente"

    class Status(models.TextChoices):
        RECEBIDO = "Recebido", "Recebido"
        PREVISTO = "Previsto", "Previsto"

    cliente = models.ForeignKey(EntryClient, on_delete=models.PROTECT, related_name="entradas")
    data_recebimento = models.DateField(null=True, blank=True)
    data_vencimento = models.DateField(null=True, blank=True)
    nf = models.CharField(max_length=30, choices=NfStatus.choices, default=NfStatus.DESNECESSARIO)
    observacoes = models.TextField(blank=True)
    produto = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PREVISTO)
    valor = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-data_recebimento", "-created_at"]
        verbose_name = "Entrada"
        verbose_name_plural = "Entradas"

    def __str__(self):
        return str(self.cliente) or f"Entrada {self.pk}"
