from django.db import models

from apps.core.models import TenantAwareModel


class MarketPrice(models.Model):
    instrument = models.ForeignKey("catalog.MarketInstrument", on_delete=models.CASCADE, related_name="market_prices")
    source = models.ForeignKey("catalog.PriceSource", on_delete=models.PROTECT, related_name="market_prices")
    price_date = models.DateField()
    price_time = models.TimeField(null=True, blank=True)
    open_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    high_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    low_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    close_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    settlement_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    volume = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ["-price_date"]
        constraints = [models.UniqueConstraint(fields=["instrument", "source", "price_date", "price_time"], name="uq_market_price_ref")]


class FxRate(models.Model):
    base_currency = models.CharField(max_length=10)
    quote_currency = models.CharField(max_length=10)
    rate_date = models.DateField()
    rate = models.DecimalField(max_digits=18, decimal_places=6)

    class Meta:
        ordering = ["-rate_date"]
        constraints = [models.UniqueConstraint(fields=["base_currency", "quote_currency", "rate_date"], name="uq_fx_rate")]


class HistoricalQuote(models.Model):
    """Cache imutável de fechamentos por (símbolo, data).

    Cotações históricas não mudam: grava uma vez, lê para sempre. Evita
    sobrecarregar fontes externas — a busca acontece no máximo uma vez por
    par (símbolo, data). `close=None` registra uma busca sem resultado
    (miss em cache) e pode ser revalidada quando ficar velha.
    """

    symbol = models.CharField(max_length=80)
    quote_date = models.DateField()
    close = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    source = models.CharField(max_length=20, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["symbol", "-quote_date"]
        constraints = [
            models.UniqueConstraint(fields=["symbol", "quote_date"], name="uq_historicalquote_symbol_date"),
        ]
        indexes = [models.Index(fields=["symbol", "quote_date"])]

    def __str__(self):
        return f"{self.symbol} @ {self.quote_date}: {self.close}"


class ConabBasisSnapshot(models.Model):
    """Snapshot único do dataset sazonal de basis (CONAB + CBOT + PTAX).

    O coletor (`collect_conab_basis`) regrava `payload` periodicamente; o
    endpoint público serve sempre a última linha. Assim, quando a CONAB
    divulga novas semanas (inclusive virada de ano), o dashboard passa a
    exibi-las sem rebuild do front. Mantemos histórico de snapshots para
    auditoria/rollback; a leitura usa sempre o `updated_at` mais recente.
    """

    payload = models.JSONField()
    week_count = models.PositiveIntegerField(default=0)
    last_week = models.CharField(max_length=10, blank=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"ConabBasisSnapshot {self.updated_at:%Y-%m-%d %H:%M} ({self.week_count} semanas)"


class SojaCrushSnapshot(models.Model):
    """Snapshot do dataset de esmagamento/capacidade de soja (USDA PSD + ABIOVE).

    Mesma estratégia do `ConabBasisSnapshot`: o coletor (`collect_soja_crush`)
    regrava `payload` periodicamente e o endpoint público serve sempre a
    última linha. Quando o USDA divulga novo ano-safra (circular Oilseeds) ou
    a ABIOVE atualiza a capacidade instalada, o dashboard passa a exibir sem
    rebuild do front. Histórico mantido para auditoria/rollback.
    """

    payload = models.JSONField()
    latest_market_year = models.PositiveIntegerField(default=0)
    source_note = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"SojaCrushSnapshot {self.updated_at:%Y-%m-%d %H:%M} (MY{self.latest_market_year})"


class ForwardCoverageSnapshot(models.Model):
    """Snapshot da cobertura forward das fábricas (compra antecipada).

    Provider-agnóstico: BR via SAFRAS Data Feed (comercialização/cobertura),
    China via Kpler (fluxo forward de embarque como proxy de compra). Sem
    credencial, o provedor entra como "não configurado" e o payload diz isso
    — nunca inventa série. Mesma estratégia de snapshot do
    `SojaCrushSnapshot`: o coletor regrava, o endpoint serve a última linha.
    """

    payload = models.JSONField()
    providers_note = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"ForwardCoverageSnapshot {self.updated_at:%Y-%m-%d %H:%M}"


class BasisSeries(TenantAwareModel):
    crop = models.ForeignKey("catalog.Crop", on_delete=models.PROTECT, related_name="basis_series")
    region = models.CharField(max_length=120)
    basis_date = models.DateField()
    value = models.DecimalField(max_digits=18, decimal_places=4)
    source = models.ForeignKey("catalog.PriceSource", on_delete=models.PROTECT, related_name="basis_series")

    class Meta:
        ordering = ["-basis_date"]
        indexes = [models.Index(fields=["tenant", "crop", "basis_date"])]
