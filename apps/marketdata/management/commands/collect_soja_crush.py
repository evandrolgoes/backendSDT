from django.core.management.base import BaseCommand, CommandError

from apps.marketdata.soja_crush import collect_and_store


class Command(BaseCommand):
    help = (
        "Coleta esmagamento/cobertura das fábricas de soja (USDA PSD + "
        "capacidade ABIOVE) e grava um novo SojaCrushSnapshot. Idempotente: "
        "rode quantas vezes quiser; novo ano-safra do USDA entra sozinho."
    )

    def handle(self, *args, **options):
        try:
            snapshot = collect_and_store()
        except Exception as exc:
            raise CommandError(f"Falha ao coletar esmagamento de soja: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Snapshot #{snapshot.id} gravado: último ano-safra MY"
                f"{snapshot.latest_market_year or '—'}."
            )
        )
