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


class BasisSeries(TenantAwareModel):
    crop = models.ForeignKey("catalog.Crop", on_delete=models.PROTECT, related_name="basis_series")
    region = models.CharField(max_length=120)
    basis_date = models.DateField()
    value = models.DecimalField(max_digits=18, decimal_places=4)
    source = models.ForeignKey("catalog.PriceSource", on_delete=models.PROTECT, related_name="basis_series")

    class Meta:
        ordering = ["-basis_date"]
        indexes = [models.Index(fields=["tenant", "crop", "basis_date"])]
