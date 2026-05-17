from django.core.management.base import BaseCommand

from apps.strategies.alerts import evaluate_trigger_alerts


class Command(BaseCommand):
    help = "Avalia gatilhos derivativos e envia e-mail quando um é atingido."

    def handle(self, *args, **options):
        stats = evaluate_trigger_alerts()
        self.stdout.write(
            self.style.SUCCESS(
                "Gatilhos avaliados: "
                f"{stats['evaluated']} | atingidos: {stats['hits']} | "
                f"alertas novos: {stats['alerts']} | e-mails: {stats['emails']} | "
                f"re-armados: {stats['rearmed']}"
            )
        )
