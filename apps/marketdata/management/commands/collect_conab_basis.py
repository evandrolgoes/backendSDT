from django.core.management.base import BaseCommand, CommandError

from apps.marketdata.conab_basis import collect_and_store


class Command(BaseCommand):
    help = (
        "Coleta o dataset sazonal de basis (CONAB XMLA + CBOT + PTAX) e grava "
        "um novo ConabBasisSnapshot. Idempotente: rode quantas vezes quiser; "
        "novas semanas da CONAB (inclusive virada de ano) entram sozinhas."
    )

    def handle(self, *args, **options):
        try:
            snapshot = collect_and_store()
        except Exception as exc:
            raise CommandError(f"Falha ao coletar basis CONAB: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Snapshot #{snapshot.id} gravado: {snapshot.week_count} semanas, "
                f"última {snapshot.last_week or '—'}."
            )
        )
