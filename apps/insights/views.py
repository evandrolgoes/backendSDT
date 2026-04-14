from rest_framework import permissions, response, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView

from .models import MissingFieldIgnoredConfig, TableColumnConfig
from .serializers import MissingFieldIgnoredConfigMutationSerializer
from .services import (
    build_insights_payload,
    build_missing_fields_payload,
    get_missing_fields_config_option,
    get_missing_fields_config_payload,
)


class TableColumnConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _normalize_keys(self, value):
        if not isinstance(value, list):
            return []
        return [str(k) for k in value if k]

    def _resolve_tenant(self, request, tenant_id=None):
        """Return the tenant to use. Superusers may pass tenant_id; others use own tenant."""
        if tenant_id is not None:
            if not request.user.is_superuser:
                raise PermissionDenied("Somente superuser pode salvar para outros tenants.")
            from apps.accounts.models import Tenant
            try:
                return Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                return None
        return request.user.tenant

    def get(self, request, *args, **kwargs):
        configs = TableColumnConfig.objects.filter(tenant=request.user.tenant)
        payload = {
            cfg.resource: {
                "orderedKeys": cfg.ordered_keys,
                "hiddenKeys": cfg.hidden_keys,
            }
            for cfg in configs
        }
        return response.Response(payload)

    def put(self, request, *args, **kwargs):
        resource = str(request.data.get("resource") or "").strip()
        if not resource:
            return response.Response(
                {"detail": "Campo 'resource' obrigatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant_id = request.data.get("tenant_id")
        tenant = self._resolve_tenant(request, tenant_id)
        if tenant is None:
            return response.Response({"detail": "Tenant nao encontrado."}, status=status.HTTP_404_NOT_FOUND)

        ordered_keys = self._normalize_keys(request.data.get("orderedKeys", []))
        hidden_keys = self._normalize_keys(request.data.get("hiddenKeys", []))

        cfg, created = TableColumnConfig.objects.update_or_create(
            tenant=tenant,
            resource=resource,
            defaults={"ordered_keys": ordered_keys, "hidden_keys": hidden_keys},
        )

        return response.Response(
            {"resource": resource, "orderedKeys": cfg.ordered_keys, "hiddenKeys": cfg.hidden_keys},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):
        resource = str(request.data.get("resource") or "").strip()
        if not resource:
            return response.Response(
                {"detail": "Campo 'resource' obrigatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant_id = request.data.get("tenant_id")
        tenant = self._resolve_tenant(request, tenant_id)
        if tenant is None:
            return response.Response({"detail": "Tenant nao encontrado."}, status=status.HTTP_404_NOT_FOUND)
        TableColumnConfig.objects.filter(tenant=tenant, resource=resource).delete()
        return response.Response(status=status.HTTP_204_NO_CONTENT)


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
