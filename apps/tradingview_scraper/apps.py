from django.apps import AppConfig


class TradingviewScraperConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tradingview_scraper"
    verbose_name = "TradingView Scraper"

    def ready(self):
        from .scheduler import start_tradingview_sync_job

        start_tradingview_sync_job()
