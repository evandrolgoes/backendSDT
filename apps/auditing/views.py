from apps.core.viewsets import TenantScopedModelViewSet
from rest_framework.exceptions import PermissionDenied

from .models import Attachment, AuditLog
from .serializers import AttachmentSerializer, AuditLogSerializer


class AuditLogViewSet(TenantScopedModelViewSet):
    queryset = AuditLog.objects.select_related("tenant", "user", "content_type").all()
    serializer_class = AuditLogSerializer
    filterset_fields = ["tenant", "user", "action", "content_type", "formulario", "object_id"]
    search_fields = ["description", "formulario"]
    http_method_names = ["get", "head", "options", "delete"]

    def get_queryset(self):
        queryset = super().get_queryset()
        created_at_from = self.request.query_params.get("created_at_from")
        created_at_to = self.request.query_params.get("created_at_to")

        if created_at_from:
            queryset = queryset.filter(created_at__date__gte=created_at_from)
        if created_at_to:
            queryset = queryset.filter(created_at__date__lte=created_at_to)

        return queryset

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied("Somente superuser pode excluir registros do log.")
        return super().destroy(request, *args, **kwargs)


class AttachmentViewSet(TenantScopedModelViewSet):
    queryset = Attachment.objects.select_related("tenant", "uploaded_by", "content_type").all()
    serializer_class = AttachmentSerializer
    filterset_fields = ["tenant", "uploaded_by", "content_type"]

    def perform_create(self, serializer):
        extra = {"uploaded_by": self.request.user}
        if not self.request.user.is_superuser:
            extra["tenant"] = self.request.user.tenant
        serializer.save(**extra)
