from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class CashBalance(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    grupo = models.ForeignKey(
        "clients.EconomicGroup",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cash_balances",
    )
    subgrupo = models.ForeignKey(
        "clients.SubGroup",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cash_balances",
    )
    conta = models.CharField(max_length=120, blank=True)
    banco = models.CharField(max_length=120, blank=True)
    saldo = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    moeda = models.CharField(max_length=20, blank=True, default="R$")
    considerar_no_fluxo = models.BooleanField(default=True)
    obs = models.TextField(blank=True)

    class Meta:
        ordering = ["banco", "conta", "-created_at"]
        verbose_name = "Caixa disponivel e aplicacao"
        verbose_name_plural = "Caixa disponivel e aplicacoes"
        indexes = [
            models.Index(fields=["tenant", "banco"]),
            models.Index(fields=["tenant", "considerar_no_fluxo"]),
        ]

    def __str__(self):
        parts = [self.banco, self.conta]
        label = " - ".join([p for p in parts if p])
        return label or f"Caixa {self.pk}"
