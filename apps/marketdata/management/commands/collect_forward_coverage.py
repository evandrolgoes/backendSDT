from django.core.management.base import BaseCommand, CommandError

from apps.marketdata.forward_coverage import collect_and_store


class Command(BaseCommand):
    help = (
        "Coleta a cobertura forward das fábricas (SAFRAS p/ Brasil, Kpler p/ "
        "China) e grava um ForwardCoverageSnapshot. Sem credencial o provedor "
        "entra como 'não configurado' — não inventa série."
    )

    def handle(self, *args, **options):
        try:
            snapshot = collect_and_store()
        except Exception as exc:
            raise CommandError(f"Falha ao coletar cobertura forward: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Snapshot #{snapshot.id} gravado: {snapshot.providers_note}."
            )
        )
