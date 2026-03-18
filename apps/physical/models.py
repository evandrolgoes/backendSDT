from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class PhysicalQuote(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    cotacao = models.DecimalField(max_digits=18, decimal_places=4)
    cultura_texto = models.CharField(max_length=100)
    data_pgto = models.DateField(null=True, blank=True)
    data_report = models.DateField(null=True, blank=True)
    localidade = models.CharField(max_length=120, blank=True)
    moeda_unidade = models.CharField(max_length=30)
    safra = models.ForeignKey("clients.CropSeason", null=True, blank=True, on_delete=models.SET_NULL, related_name="cotacoes_fisico")
    obs = models.TextField(blank=True)

    class Meta:
        ordering = ["-data_report", "-created_at"]

    def __str__(self):
        return f"{self.cultura_texto} - {self.data_report or self.created_at.date()}"


class BudgetCost(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    subgrupo = models.ForeignKey("clients.SubGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="custos_orcamento")
    grupo = models.ForeignKey("clients.EconomicGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="custos_orcamento")
    cultura = models.ForeignKey("catalog.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="custos_orcamento")
    safra = models.ForeignKey("clients.CropSeason", null=True, blank=True, on_delete=models.SET_NULL, related_name="custos_orcamento")
    considerar_na_politica_de_hedge = models.BooleanField(default=False)
    grupo_despesa = models.CharField(max_length=120)
    moeda = models.CharField(max_length=20)
    valor = models.DecimalField(max_digits=18, decimal_places=2)
    obs = models.TextField(blank=True)

    class Meta:
        ordering = ["grupo_despesa", "-created_at"]

    def __str__(self):
        return f"{self.grupo_despesa} - {self.valor}"


class ActualCost(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    subgrupo = models.ForeignKey("clients.SubGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="custos_realizados")
    grupo = models.ForeignKey("clients.EconomicGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="custos_realizados")
    cultura = models.ForeignKey("catalog.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="custos_realizados")
    safra = models.ForeignKey("clients.CropSeason", null=True, blank=True, on_delete=models.SET_NULL, related_name="custos_realizados")
    grupo_despesa = models.CharField(max_length=120)
    moeda = models.CharField(max_length=20)
    valor = models.DecimalField(max_digits=18, decimal_places=2)
    obs = models.TextField(blank=True)

    class Meta:
        ordering = ["grupo_despesa", "-created_at"]

    def __str__(self):
        return f"{self.grupo_despesa} - {self.valor}"


class PhysicalSale(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    cultura = models.ForeignKey("catalog.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="vendas_fisico")
    grupos = models.ManyToManyField("clients.EconomicGroup", blank=True, related_name="vendas_fisico")
    subgrupos = models.ManyToManyField("clients.SubGroup", blank=True, related_name="vendas_fisico")
    safra = models.ForeignKey("clients.CropSeason", null=True, blank=True, on_delete=models.SET_NULL, related_name="vendas_fisico")
    basis_valor = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    basis_moeda = models.CharField(max_length=30, blank=True)
    bolsa_ref = models.CharField(max_length=50, blank=True)
    cif_fob = models.CharField(max_length=20, blank=True)
    compra_venda = models.CharField(max_length=20, blank=True)
    contraparte = models.ForeignKey("clients.Counterparty", null=True, blank=True, on_delete=models.SET_NULL, related_name="vendas_fisico")
    contrato_bolsa = models.CharField(max_length=120, blank=True)
    cotacao_bolsa_ref = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    cultura_produto = models.CharField(max_length=100, blank=True)
    data_entrega = models.DateField(null=True, blank=True)
    data_negociacao = models.DateField(null=True, blank=True)
    data_pagamento = models.DateField(null=True, blank=True)
    dolar_de_venda = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    faturamento_total_contrato = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    moeda_contrato = models.CharField(max_length=20, blank=True)
    objetivo_venda_dolarizada = models.CharField(max_length=120, blank=True)
    pf_paf = models.CharField(max_length=20, blank=True)
    preco = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    unidade_contrato = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    volume_fisico = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ["-data_negociacao", "-created_at"]

    def __str__(self):
        return f"Venda fisico {self.id}"
