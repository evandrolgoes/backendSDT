from decimal import Decimal

from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class Strategy(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    data_validade = models.DateField(null=True, blank=True)
    descricao_estrategia = models.TextField(blank=True)
    grupo = models.ForeignKey("clients.EconomicGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="estrategias")
    subgrupo = models.ForeignKey("clients.SubGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="estrategias")
    obs = models.TextField(blank=True)
    status = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-data_validade", "-created_at"]

    def __str__(self):
        return self.descricao_estrategia[:80] or f"Estrategia {self.id}"


class StrategyTrigger(models.Model):
    estrategia = models.ForeignKey(Strategy, null=True, blank=True, on_delete=models.SET_NULL, related_name="gatilhos")
    acima_abaixo = models.CharField(max_length=20, blank=True)
    contrato_bolsa = models.CharField(max_length=120, blank=True)
    cultura = models.ForeignKey("catalog.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="gatilhos")
    codigo_derivativo = models.CharField(max_length=120, blank=True)
    codigos_estrategia = models.JSONField(default=list, blank=True)
    grupos = models.ManyToManyField("clients.EconomicGroup", blank=True, related_name="gatilhos")
    subgrupos = models.ManyToManyField("clients.SubGroup", blank=True, related_name="gatilhos")
    posicao = models.CharField(max_length=20, blank=True)
    produto_bolsa = models.CharField(max_length=120, blank=True)
    status_gatilho = models.CharField(max_length=50, blank=True)
    strike_alvo = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    tipo_fis_der = models.CharField(max_length=20, blank=True)
    unidade = models.CharField(max_length=20, blank=True)
    volume = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    obs = models.TextField(blank=True)
    status = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.contrato_bolsa or f"Gatilho {self.id}"


class HedgePolicy(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    cultura = models.ForeignKey("catalog.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="politicas_hedge")
    grupos = models.ManyToManyField("clients.EconomicGroup", blank=True, related_name="politicas_hedge")
    subgrupos = models.ManyToManyField("clients.SubGroup", blank=True, related_name="politicas_hedge")
    safra = models.ForeignKey("clients.CropSeason", null=True, blank=True, on_delete=models.SET_NULL, related_name="politicas_hedge")
    insumos_travados_maximo = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    insumos_travados_minimo = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    margem_alvo_minimo = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    mes_ano = models.DateField(null=True, blank=True)
    obs = models.TextField(blank=True)
    vendas_x_custo_maximo = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    vendas_x_custo_minimo = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    vendas_x_prod_total_maximo = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    vendas_x_prod_total_minimo = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ["-mes_ano", "-created_at"]

    def __str__(self):
        return f"Politica {self.id}"


class CropBoard(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    cultura = models.ForeignKey("catalog.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="quadros_safra")
    grupo = models.ForeignKey("clients.EconomicGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="quadros_safra")
    subgrupo = models.ForeignKey("clients.SubGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="quadros_safra")
    safra = models.ForeignKey("clients.CropSeason", null=True, blank=True, on_delete=models.SET_NULL, related_name="quadros_safra")
    localidade = models.JSONField(default=list, blank=True)
    area = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    bolsa_ref = models.CharField(max_length=50, blank=True)
    monitorar_vc = models.BooleanField(default=False)
    obs = models.TextField(blank=True)
    produtividade = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    producao_total = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    criar_politica_hedge = models.BooleanField(default=False)
    unidade_producao = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Quadro safra {self.id}"

    def save(self, *args, **kwargs):
        if self.area is not None and self.produtividade is not None:
            self.producao_total = Decimal(self.area) * Decimal(self.produtividade)
        else:
            self.producao_total = None
        super().save(*args, **kwargs)
