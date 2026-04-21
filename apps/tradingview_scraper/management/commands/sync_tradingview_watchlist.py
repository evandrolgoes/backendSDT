from django.core.management.base import BaseCommand, CommandError

from apps.tradingview_scraper.services import sync_auto_contracts


class Command(BaseCommand):
    help = "Sincroniza os contratos futuros auto-gerados via TradingView Scanner API."

    def handle(self, *args, **options):
        try:
            payload = sync_auto_contracts()
        except Exception as exc:
            raise CommandError(f"Falha ao sincronizar contratos: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Contratos sincronizados: "
                f"{payload['quotes_resolved']}/{payload['symbols_generated']} cotacoes resolvidas."
            )
        )

