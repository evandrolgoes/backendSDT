from rest_framework import permissions, response, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView

from .models import MissingFieldIgnoredConfig
from .serializers import MissingFieldIgnoredConfigMutationSerializer
from .services import (
    build_insights_payload,
    build_missing_fields_payload,
    get_missing_fields_config_option,
    get_missing_fields_config_payload,
)


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


class MissingFieldsIgnoredConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _ensure_superuser(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied("Somente superuser pode gerenciar os campos ignorados.")

    def get(self, request, *args, **kwargs):
        self._ensure_superuser(request)
        return response.Response(get_missing_fields_config_payload(request))

    def post(self, request, *args, **kwargs):
        self._ensure_superuser(request)
        serializer = MissingFieldIgnoredConfigMutationSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        option = get_missing_fields_config_option(
            request,
            serializer.validated_data["resource"],
            serializer.validated_data["field_name"],
        )
        if option is None:
            return response.Response(
                {"detail": "Recurso ou campo invalido para configuracao de pendencias."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config, created = MissingFieldIgnoredConfig.objects.get_or_create(
            tenant=request.user.tenant,
            resource=option["resource"],
            field_name=option["field_name"],
            defaults={
                "resource_label": option["resource_label"],
                "field_label": option["field_label"],
            },
        )
        if not created:
            config.resource_label = option["resource_label"]
            config.field_label = option["field_label"]
            config.save(update_fields=["resource_label", "field_label", "updated_at"])

        return response.Response(get_missing_fields_config_payload(request), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        self._ensure_superuser(request)
        serializer = MissingFieldIgnoredConfigMutationSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        MissingFieldIgnoredConfig.objects.filter(
            tenant=request.user.tenant,
            resource=serializer.validated_data["resource"],
            field_name=serializer.validated_data["field_name"],
        ).delete()
        return response.Response(get_missing_fields_config_payload(request), status=status.HTTP_200_OK)
