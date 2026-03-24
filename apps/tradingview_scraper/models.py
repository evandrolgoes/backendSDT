from django.db import models

from apps.core.models import TimeStampedModel


class TradingViewWatchlistQuote(TimeStampedModel):
    source_url = models.URLField()
    watchlist_id = models.CharField(max_length=50)
    watchlist_name = models.CharField(max_length=120, blank=True)
    section_name = models.CharField(max_length=120, blank=True)
    symbol = models.CharField(max_length=80)
    provider = models.CharField(max_length=40, blank=True)
    ticker = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    change_percent = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    change_value = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    currency = models.CharField(max_length=20, blank=True)
    instrument_type = models.CharField(max_length=40, blank=True)
    instrument_subtype = models.CharField(max_length=40, blank=True)
    sort_order = models.PositiveIntegerField()
    synced_at = models.DateTimeField()
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["sort_order", "symbol"]
        constraints = [
            models.UniqueConstraint(fields=["source_url", "symbol"], name="uq_tradingview_watchlist_quote_source_symbol"),
        ]

    def __str__(self):
        return self.symbol

