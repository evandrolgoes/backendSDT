from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class DerivativeOperation(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    subgrupo = models.ForeignKey("clients.SubGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    grupo = models.ForeignKey("clients.EconomicGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    cultura = models.ForeignKey("catalog.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    destino_cultura = models.ForeignKey("catalog.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos_destino")
    safra = models.ForeignKey("clients.CropSeason", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    cod_operacao_mae = models.CharField(max_length=120, blank=True)
    bolsa_ref = models.CharField(max_length=60, blank=True)
    status_operacao = models.CharField(max_length=30, blank=True, default="Em aberto")
    contraparte = models.ForeignKey("clients.Counterparty", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    data_contratacao = models.DateField(null=True, blank=True)
    data_liquidacao = models.DateField(null=True, blank=True)
    contrato_derivativo = models.CharField(max_length=120, blank=True)
    dolar_ptax_vencimento = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    moeda_ou_cmdtye = models.CharField(max_length=30, blank=True)
    moeda_unidade = models.CharField(max_length=30, blank=True)
    nome_da_operacao = models.CharField(max_length=120, blank=True)
    unidade = models.CharField(max_length=20, blank=True)
    grupo_montagem = models.CharField(max_length=20, blank=True)
    tipo_derivativo = models.CharField(max_length=30, blank=True)
    numero_lotes = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    strike_montagem = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    custo_total_montagem_brl = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    strike_liquidacao = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    ajustes_totais_brl = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    ajustes_totais_usd = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    ordem = models.PositiveIntegerField(default=1)
    volume_financeiro_moeda = models.CharField(max_length=20, blank=True)
    volume_financeiro_valor_moeda_original = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    volume = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ["cod_operacao_mae", "ordem", "id"]

    def __str__(self):
        return self.cod_operacao_mae or f"Operacao derivativo {self.id}"
