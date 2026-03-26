from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class DerivativeOperation(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    ativo = models.ForeignKey("catalog.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos", verbose_name="Ativo")
    ajustes_totais_brl = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    ajustes_totais_usd = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    bolsa_ref = models.CharField(max_length=60, blank=True)
    cod_operacao_mae = models.CharField(max_length=120, blank=True)
    contrato_derivativo = models.CharField(max_length=120, blank=True)
    contraparte = models.ForeignKey("clients.Counterparty", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    custo_total_montagem_brl = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    data_contratacao = models.DateField(null=True, blank=True)
    data_liquidacao = models.DateField(null=True, blank=True)
    destino_cultura = models.ForeignKey("catalog.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos_destino")
    dolar_ptax_vencimento = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    grupo = models.ForeignKey("clients.EconomicGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    moeda_ou_cmdtye = models.CharField(max_length=30, blank=True)
    nome_da_operacao = models.CharField(max_length=120, blank=True)
    numero_lotes = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    obs = models.TextField(blank=True, verbose_name="Obs")
    ordem = models.PositiveIntegerField(default=1)
    posicao = models.CharField(max_length=20, blank=True, verbose_name="Posicao")
    safra = models.ForeignKey("clients.CropSeason", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    swap_divida = models.CharField(max_length=10, blank=True, verbose_name="Se for Moeda Swap de Divida")
    strike_moeda_unidade = models.CharField(max_length=30, blank=True, verbose_name="Strike moeda unidade")
    status_operacao = models.CharField(max_length=30, blank=True, default="Em aberto")
    strike_liquidacao = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    strike_montagem = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    subgrupo = models.ForeignKey("clients.SubGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="derivativos")
    tipo_derivativo = models.CharField(max_length=30, blank=True)
    volume_financeiro_moeda = models.CharField(max_length=20, blank=True)
    volume_financeiro_valor = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, verbose_name="Volume financeiro valor")
    volume_fisico_unidade = models.CharField(max_length=20, blank=True, verbose_name="Volume fisico unidade")
    volume_fisico_valor = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name="Volume fisico valor")

    class Meta:
        ordering = ["cod_operacao_mae", "ordem", "id"]

    def __str__(self):
        return self.cod_operacao_mae or f"Operacao derivativo {self.id}"
