from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class DerivativeOperation(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    subgrupo = models.ForeignKey("clients.SubGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    grupo = models.ForeignKey("clients.EconomicGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    cultura = models.ForeignKey("catalog.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    safra = models.ForeignKey("clients.CropSeason", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    cod_operacao_mae = models.CharField(max_length=120, blank=True)
    compra_venda = models.CharField(max_length=20, blank=True)
    contraparte = models.ForeignKey("clients.Counterparty", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    contrato_derivativo = models.CharField(max_length=120, blank=True)
    custo_total_montagem = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    data_contratacao = models.DateField(null=True, blank=True)
    data_liquidacao = models.DateField(null=True, blank=True)
    liquidacao_ajuste_total_moeda_original = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    liquidacao_ajuste_total_brl = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    liquidacao_dolar_ptax = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    moeda_ou_cmdtye = models.CharField(max_length=30, blank=True)
    moeda_unidade = models.CharField(max_length=30, blank=True)
    nome_da_operacao = models.CharField(max_length=120, blank=True)
    tipo_derivativo = models.CharField(max_length=30, blank=True)
    unidade = models.CharField(max_length=20, blank=True)
    volume_financeiro_moeda = models.CharField(max_length=20, blank=True)
    volume_financeiro_valor_moeda_original = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    volume_financeiro_valor_moeda_brl = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    volume_fisico = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    volume_fisico_unidade_padrao_cultura = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ["-data_contratacao", "-created_at"]

    def __str__(self):
        return self.contrato_derivativo or f"Derivativo {self.id}"
