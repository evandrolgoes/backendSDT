from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from rest_framework import parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.auditing.context import suppress_audit_signals
from apps.auditing.models import Attachment
from apps.auditing.serializers import AttachmentSerializer
from apps.core.viewsets import TenantScopedModelViewSet

from .models import Anotacao
from .serializers import AnotacaoSerializer


def anotacoes_health(_request):
    return JsonResponse({"status": "ok", "app": "anotacoes"})


class AnotacaoViewSet(TenantScopedModelViewSet):
    queryset = Anotacao.objects.select_related("tenant", "created_by", "modificado_por").prefetch_related("grupos", "subgrupos").all()
    serializer_class = AnotacaoSerializer
    filterset_fields = ["modificado_por"]
    search_fields = ["titulo", "participantes", "conteudo_html", "grupos__grupo", "subgrupos__subgrupo"]

    def _build_save_kwargs(self, serializer):
        save_kwargs = {}
        if hasattr(serializer.Meta.model, "tenant"):
            save_kwargs["tenant"] = self.request.user.tenant
        if hasattr(serializer.Meta.model, "created_by") and serializer.instance is None:
            save_kwargs["created_by"] = self.request.user
        if hasattr(serializer.Meta.model, "modificado_por") and self.request.user.is_authenticated:
            save_kwargs["modificado_por"] = self.request.user
        return save_kwargs

    def perform_create(self, serializer):
        with suppress_audit_signals():
            instance = serializer.save(**self._build_save_kwargs(serializer))
        self._create_audit_log("criado", instance, before={}, after=self._serialize_instance_for_log(instance))

    def perform_update(self, serializer):
        before = self._serialize_instance_for_log(serializer.instance)
        with suppress_audit_signals():
            instance = serializer.save(**self._build_save_kwargs(serializer))
        self._create_audit_log("alterado", instance, before=before, after=self._serialize_instance_for_log(instance))

    @action(detail=True, methods=["get", "post"], parser_classes=[parsers.MultiPartParser, parsers.FormParser])
    def attachments(self, request, pk=None):
        instance = self.get_object()
        content_type = ContentType.objects.get_for_model(Anotacao)
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
