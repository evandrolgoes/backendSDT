import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsMasterAdmin

from .services import generate_market_summary

logger = logging.getLogger(__name__)


class MarketSummaryGenerateView(APIView):
    permission_classes = [IsMasterAdmin]

    def post(self, request, *args, **kwargs):
        try:
            payload = generate_market_summary(request.data or {})
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            logger.exception("Erro inesperado ao gerar resumo de mercado.")
            return Response(
                {
                    "detail": str(exc) if settings.DEBUG else "Nao foi possivel gerar o resumo de mercado agora."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(payload, status=status.HTTP_200_OK)
