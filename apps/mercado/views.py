import urllib.request
import urllib.parse

from django.http import JsonResponse, HttpResponse
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import parsers, status
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditing.context import suppress_audit_signals
from apps.auditing.models import Attachment
from apps.auditing.serializers import AttachmentSerializer
from apps.core.viewsets import TenantScopedModelViewSet

from .models import MarketNewsPost
from .serializers import MarketNewsPostListSerializer, MarketNewsPostSerializer
from .services import build_fund_position_payload


def mercado_health(_request):
    return JsonResponse({"status": "ok", "app": "mercado"})


ALLOWED_YAHOO_SYMBOLS = {
    "ZS=F", "ZC=F", "ZW=F", "ZM=F", "ZL=F", "SB=F",
}


def yahoo_finance_proxy(request):
    symbol = request.GET.get("symbol", "").strip()
    period1 = request.GET.get("period1", "").strip()
    period2 = request.GET.get("period2", "").strip()

    if not symbol or not period1 or not period2:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    if symbol not in ALLOWED_YAHOO_SYMBOLS:
        return JsonResponse({"error": "Symbol not allowed"}, status=400)

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
        f"?period1={period1}&period2={period2}&interval=1d&includePrePost=false&events=history"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()
        return HttpResponse(data, content_type="application/json")
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=502)


class FundPositionSeriesView(APIView):
    def get(self, request, *args, **kwargs):
        series_id = request.query_params.get("series", "soja")
        try:
            payload = build_fund_position_payload(series_id=series_id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(payload, status=status.HTTP_200_OK)


class MarketNewsPostPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and (user.is_superuser or user.is_tenant_admin()))


class MarketNewsPostViewSet(TenantScopedModelViewSet):
    queryset = MarketNewsPost.objects.select_related("tenant", "created_by", "published_by").all()
    serializer_class = MarketNewsPostSerializer
    permission_classes = [MarketNewsPostPermission]
    filterset_fields = ["status_artigo", "published_by"]
    search_fields = ["titulo", "categorias", "conteudo_html"]

    def get_serializer_class(self):
        if self.action == "list":
            return MarketNewsPostListSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = self.queryset.all()
        user = getattr(self.request, "user", None)
        public_read = str(self.request.query_params.get("public", "")).strip().lower() in {"1", "true", "yes"}
        if public_read:
            queryset = queryset.filter(status_artigo=MarketNewsPost.STATUS_PUBLISHED)
        elif not user or not user.is_authenticated:
            queryset = queryset.filter(status_artigo=MarketNewsPost.STATUS_PUBLISHED)
        else:
            queryset = super().get_queryset()
            if not (user.is_superuser or user.is_tenant_admin()):
                queryset = queryset.filter(status_artigo=MarketNewsPost.STATUS_PUBLISHED)

        if self.action == "list":
            queryset = queryset.defer("conteudo_html")
        return queryset

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

    def perform_destroy(self, instance):
        before = self._serialize_instance_for_log(instance)
        self._create_audit_log("excluido", instance, before=before, after={})

        content_type = ContentType.objects.get_for_model(MarketNewsPost)
        attachments = Attachment.objects.filter(
            tenant=instance.tenant,
            content_type=content_type,
            object_id=instance.pk,
        )

        with suppress_audit_signals():
            for attachment in attachments:
                if getattr(attachment, "file", None):
                    attachment.file.delete(save=False)
            attachments.delete()
            if getattr(instance, "audio", None):
                instance.audio.delete(save=False)
            instance.delete()

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
            Attachment.create_from_upload(
                tenant=instance.tenant,
                uploaded_by=request.user,
                content_type=content_type,
                object_id=instance.pk,
                uploaded_file=uploaded_file,
            )
            for uploaded_file in files
        ]
        return Response(
            AttachmentSerializer(created, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
