from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.auditing.context import suppress_audit_signals
from apps.auditing.models import Attachment
from apps.auditing.serializers import AttachmentSerializer
from apps.core.viewsets import TenantScopedModelViewSet

from .models import MarketNewsPost
from .serializers import MarketNewsPostSerializer


def mercado_health(_request):
    return JsonResponse({"status": "ok", "app": "mercado"})


class MarketNewsPostViewSet(TenantScopedModelViewSet):
    queryset = MarketNewsPost.objects.select_related("tenant", "created_by", "published_by").all()
    serializer_class = MarketNewsPostSerializer
    filterset_fields = ["status_artigo", "published_by"]
    search_fields = ["titulo", "categorias", "conteudo_html"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return queryset.filter(status_artigo=MarketNewsPost.STATUS_PUBLISHED)
        if user.is_superuser or user.is_tenant_admin():
            return queryset
        return queryset.filter(status_artigo=MarketNewsPost.STATUS_PUBLISHED)

    def _build_save_kwargs(self, serializer):
        save_kwargs = {}
        if hasattr(serializer.Meta.model, "tenant"):
            save_kwargs["tenant"] = self.request.user.tenant
        if hasattr(serializer.Meta.model, "created_by") and serializer.instance is None:
            save_kwargs["created_by"] = self.request.user
        if serializer.validated_data.get("status_artigo") != MarketNewsPost.STATUS_PUBLISHED:
            return save_kwargs

        instance = serializer.instance
        if not getattr(instance, "data_publicacao", None) and not serializer.validated_data.get("data_publicacao"):
            save_kwargs["data_publicacao"] = timezone.now()
        if not getattr(instance, "published_by_id", None) and self.request.user.is_authenticated:
            save_kwargs["published_by"] = self.request.user
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
        content_type = ContentType.objects.get_for_model(MarketNewsPost)
        queryset = Attachment.objects.filter(
            tenant=instance.tenant,
            content_type=content_type,
            object_id=instance.pk,
        ).order_by("-created_at")

        if request.method == "GET":
            return Response(AttachmentSerializer(queryset, many=True, context={"request": request}).data)

        files = request.FILES.getlist("files")
        created = [
            Attachment.objects.create(
                tenant=instance.tenant,
                uploaded_by=request.user,
                content_type=content_type,
                object_id=instance.pk,
                file=uploaded_file,
                original_name=uploaded_file.name,
            )
            for uploaded_file in files
        ]
        return Response(
            AttachmentSerializer(created, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="categories")
    def categories(self, request):
        names = []
        seen = set()
        queryset = self.filter_queryset(self.get_queryset())
        for post in queryset.iterator():
            for item in getattr(post, "categorias", []) or []:
                normalized = str(item or "").strip()
                if not normalized:
                    continue
                key = normalized.casefold()
                if key in seen:
                    continue
                seen.add(key)
                names.append(normalized)
        names.sort(key=lambda value: value.casefold())
        return Response(names)
