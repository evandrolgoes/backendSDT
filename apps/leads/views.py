from django.conf import settings
from django.core.mail import send_mail
from rest_framework import permissions, response, status
from rest_framework.views import APIView

from .serializers import LeadSerializer


class LeadCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LeadSerializer(data=request.data)
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

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            ["evandrogoes@agrosaldaterra.com.br"],
            fail_silently=False,
        )

        return response.Response(
            {"detail": "Lead cadastrado com sucesso.", "lead": serializer.data},
            status=status.HTTP_201_CREATED,
        )
