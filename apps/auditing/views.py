from io import BytesIO

from django.http import FileResponse, Http404
from apps.core.viewsets import TenantScopedModelViewSet
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

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
        uploaded_file = serializer.validated_data.pop("file", None)
        attachment = serializer.save(**extra)
        if uploaded_file is not None:
            attachment.store_uploaded_file(uploaded_file)
            attachment.save(update_fields=["file", "file_blob", "stored_content_type", "stored_size", "original_name"])


@api_view(["GET", "HEAD"])
@permission_classes([AllowAny])
def attachment_content(request, attachment_id):
    attachment = Attachment.objects.filter(pk=attachment_id).first()
    if not attachment:
        raise Http404("Attachment not found.")

    if attachment.file_blob:
        response = FileResponse(
            BytesIO(attachment.file_blob),
            content_type=attachment.stored_content_type or "application/octet-stream",
            as_attachment=False,
            filename=attachment.original_name,
        )
        response["Content-Length"] = str(attachment.stored_size or len(attachment.file_blob))
        return response

    if attachment.file:
        try:
            file_handle = attachment.file.open("rb")
        except FileNotFoundError as exc:
            raise Http404("Attachment file not found.") from exc
        response = FileResponse(
            file_handle,
            content_type=attachment.stored_content_type or "application/octet-stream",
            as_attachment=False,
            filename=attachment.original_name,
        )
        if attachment.stored_size:
            response["Content-Length"] = str(attachment.stored_size)
        return response

    raise Http404("Attachment has no content.")
