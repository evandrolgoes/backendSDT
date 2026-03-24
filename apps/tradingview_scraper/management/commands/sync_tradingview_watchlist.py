from django.core.management.base import BaseCommand, CommandError

from apps.tradingview_scraper.services import TradingViewScraperError, sync_watchlist_to_db


class Command(BaseCommand):
    help = "Sincroniza uma watchlist publica do TradingView para a tabela experimental local."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default="https://br.tradingview.com/watchlists/160853431/",
            help="URL publica da watchlist do TradingView.",
        )

    def handle(self, *args, **options):
        source_url = options["url"]

        try:
            payload = sync_watchlist_to_db(source_url)
        except TradingViewScraperError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Falha ao sincronizar a watchlist: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Watchlist sincronizada com sucesso: "
                f"{payload['watchlist_name'] or payload['watchlist_id']} "
                f"({payload['quotes_resolved']}/{payload['symbols_found']} cotacoes resolvidas)."
            )
        )

