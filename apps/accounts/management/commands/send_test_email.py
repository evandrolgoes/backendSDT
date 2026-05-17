from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Envia um e-mail de teste para validar a config SMTP em produção."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            default="evandrogoes@agrosaldaterra.com.br",
            help="Destinatário do e-mail de teste.",
        )

    def handle(self, *args, **options):
        to = options["to"]
        agora = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M:%S")

        # Mostra a config resolvida (sem expor a senha) para diagnóstico.
        self.stdout.write(
            "Config SMTP:\n"
            f"  EMAIL_BACKEND = {settings.EMAIL_BACKEND}\n"
            f"  EMAIL_HOST    = {settings.EMAIL_HOST}:{settings.EMAIL_PORT}\n"
            f"  EMAIL_USE_TLS = {settings.EMAIL_USE_TLS} | SSL = {settings.EMAIL_USE_SSL}\n"
            f"  EMAIL_HOST_USER = {settings.EMAIL_HOST_USER}\n"
            f"  EMAIL_HOST_PASSWORD = {'(definida)' if settings.EMAIL_HOST_PASSWORD else '(VAZIA!)'}\n"
            f"  DEFAULT_FROM_EMAIL = {settings.DEFAULT_FROM_EMAIL}\n"
            f"  -> enviando para {to} ..."
        )

        sent = send_mail(
            f"[HedgePosition] Teste de SMTP — {agora}",
            (
                "Este é um e-mail de teste do HedgePosition.\n\n"
                "Se você recebeu, o SMTP está configurado corretamente e os "
                "alertas de gatilho atingido serão entregues.\n"
            ),
            settings.DEFAULT_FROM_EMAIL,
            [to],
            fail_silently=False,
        )

        if sent:
            self.stdout.write(self.style.SUCCESS(f"OK — e-mail aceito pelo servidor ({sent} enviado)."))
        else:
            self.stderr.write(self.style.ERROR("Falhou — send_mail retornou 0."))
