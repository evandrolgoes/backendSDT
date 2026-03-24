from django.contrib import admin

from .models import TradingViewWatchlistQuote


@admin.register(TradingViewWatchlistQuote)
class TradingViewWatchlistQuoteAdmin(admin.ModelAdmin):
    list_display = (
        "symbol",
        "section_name",
        "price",
        "currency",
        "instrument_type",
        "watchlist_name",
        "synced_at",
    )
    list_filter = ("watchlist_name", "section_name", "currency", "instrument_type")
    search_fields = ("symbol", "ticker", "description", "section_name")
    ordering = ("sort_order", "symbol")

