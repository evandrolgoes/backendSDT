from rest_framework import permissions, response
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView

from .services import build_insights_payload, build_missing_fields_payload


class CommercialInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        payload = build_insights_payload(request)
        return response.Response(payload)


class MissingFieldsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not request.user.is_superuser and not getattr(request.user, "has_module_access", lambda *_args: False)("tool_missing_fields"):
            raise PermissionDenied("Voce nao possui acesso a ferramenta de pendencias cadastrais.")
        payload = build_missing_fields_payload(request)
        return response.Response(payload)
