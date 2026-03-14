from apps.core.viewsets import TenantScopedModelViewSet

from .models import Attachment, AuditLog
from .serializers import AttachmentSerializer, AuditLogSerializer


class AuditLogViewSet(TenantScopedModelViewSet):
    queryset = AuditLog.objects.select_related("tenant", "user", "content_type").all()
    serializer_class = AuditLogSerializer
    filterset_fields = ["tenant", "user", "action", "content_type"]
    search_fields = ["description"]


class AttachmentViewSet(TenantScopedModelViewSet):
    queryset = Attachment.objects.select_related("tenant", "uploaded_by", "content_type").all()
    serializer_class = AttachmentSerializer
    filterset_fields = ["tenant", "uploaded_by", "content_type"]

    def perform_create(self, serializer):
        extra = {"uploaded_by": self.request.user}
        if not self.request.user.is_superuser:
            extra["tenant"] = self.request.user.tenant
        serializer.save(**extra)
