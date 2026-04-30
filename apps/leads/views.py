import logging

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import mixins, permissions, response, status, viewsets

from .models import Lead
from .serializers import LeadSerializer

logger = logging.getLogger(__name__)


class LeadViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = LeadSerializer
    queryset = Lead.objects.all()

    def get_permissions(self):
        if self.action == "create":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = serializer.save()

        subject = f"Novo lead recebido - {lead.landing_page}"
        message = "\n".join(
            [
                "Um novo lead foi cadastrado na landing page.",
                "",
                f"Landing page: {lead.landing_page}",
                f"Data: {lead.data:%d/%m/%Y %H:%M}",
                f"Nome: {lead.nome}",
                f"WhatsApp: {lead.whatsapp}",
                f"E-mail: {lead.email}",
                f"Perfil: {lead.perfil}",
                f"Trabalho e ocupacao atual: {lead.trabalho_ocupacao_atual}",
                f"Empresa atual: {lead.empresa_atual}",
                f"Objetivo: {lead.objetivo}",
                f"Mensagem: {lead.mensagem or '-'}",
            ]
        )

        mail_warning = None
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                ["evandrogoes@agrosaldaterra.com.br"],
                fail_silently=False,
            )
        except Exception as exc:
            mail_warning = "Lead salvo, mas o envio de e-mail falhou."
            logger.exception("Falha ao enviar e-mail do lead %s", lead.id, exc_info=exc)

        return response.Response(
            {"detail": "Lead cadastrado com sucesso.", "lead": serializer.data, "mail_warning": mail_warning},
            status=status.HTTP_201_CREATED,
        )
