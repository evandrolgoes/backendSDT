from django.contrib.contenttypes.models import ContentType
from rest_framework import parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.auditing.models import Attachment
from apps.auditing.serializers import AttachmentSerializer
from apps.core.viewsets import TenantScopedModelViewSet

from .models import AccountsPayable
from .serializers import AccountsPayableSerializer


class AccountsPayableViewSet(TenantScopedModelViewSet):
    queryset = AccountsPayable.objects.select_related("tenant", "created_by").all()
    serializer_class = AccountsPayableSerializer
    filterset_fields = ["empresa", "conta_origem", "status", "data_pagamento", "data_vencimento"]
    search_fields = ["descricao", "empresa", "conta_origem", "obs", "status"]

    @action(detail=True, methods=["get", "post"], parser_classes=[parsers.MultiPartParser, parsers.FormParser])
    def attachments(self, request, pk=None):
        instance = self.get_object()
        content_type = ContentType.objects.get_for_model(AccountsPayable)
        queryset = Attachment.objects.filter(
            tenant=instance.tenant,
            content_type=content_type,
            object_id=instance.pk,
        ).order_by("-created_at")

        if request.method == "GET":
            return Response(AttachmentSerializer(queryset, many=True, context={"request": request}).data)

        files = request.FILES.getlist("files")
        created = [
            Attachment.create_from_upload(
                tenant=instance.tenant,
                uploaded_by=request.user,
                content_type=content_type,
                object_id=instance.pk,
                uploaded_file=uploaded_file,
            )
            for uploaded_file in files
        ]
        return Response(AttachmentSerializer(created, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)
