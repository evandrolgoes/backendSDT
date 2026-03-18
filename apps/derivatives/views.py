import json
from urllib.error import URLError
from urllib.request import urlopen

from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from rest_framework import parsers, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auditing.models import Attachment
from apps.auditing.serializers import AttachmentSerializer
from apps.core.viewsets import TenantScopedModelViewSet

from .models import DerivativeOperation
from .serializers import DerivativeOperationSerializer


def _normalize_derivative_lookup_value(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
    )


class DerivativeOperationViewSet(TenantScopedModelViewSet):
    queryset = DerivativeOperation.objects.select_related(
        "tenant", "subgrupo", "grupo", "cultura", "safra", "contraparte", "created_by"
    ).all()
    serializer_class = DerivativeOperationSerializer
    filterset_fields = ["tenant", "subgrupo", "grupo", "cultura", "safra", "contraparte", "status_operacao"]
    search_fields = ["cod_operacao_mae", "nome_da_operacao", "bolsa_ref"]

    @action(detail=True, methods=["get", "post"], parser_classes=[parsers.MultiPartParser, parsers.FormParser])
    def attachments(self, request, pk=None):
        instance = self.get_object()
        content_type = ContentType.objects.get_for_model(DerivativeOperation)
        queryset = Attachment.objects.filter(
            tenant=instance.tenant,
            content_type=content_type,
            object_id=instance.pk,
        ).order_by("-created_at")

        if request.method == "GET":
            return Response(AttachmentSerializer(queryset, many=True).data)

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
        return Response(AttachmentSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def derivative_contracts(request):
    bolsa = request.GET.get("bolsa") or ""
    normalized_bolsa = _normalize_derivative_lookup_value(bolsa)
    if not normalized_bolsa:
        return JsonResponse([], safe=False)

    url = "https://api.sheety.co/90083751cf0794f44c9730c96a94cedf/apiCotacoesSpotGetBubble/planilha1"
    try:
        with urlopen(url, timeout=20) as response:
            payload = json.load(response)
    except (URLError, TimeoutError, ValueError):
        return JsonResponse([], safe=False, status=502)

    rows = payload.get("planilha1", []) if isinstance(payload, dict) else payload
    options = []
    for row in rows if isinstance(rows, list) else []:
        normalized = {str(key).strip().lower(): value for key, value in row.items()}
        bolsa_value = (
            normalized.get("bolsa")
            or normalized.get("produto/bolsa")
            or normalized.get("produto_bolsa")
            or normalized.get("bolsa ref")
            or normalized.get("bolsa_ref")
            or ""
        )
        if _normalize_derivative_lookup_value(bolsa_value) != normalized_bolsa:
            continue

        contract = (
            normalized.get("ctrbolsa")
            or normalized.get("ctr bolsa")
            or normalized.get("ctr_bolsa")
            or normalized.get("contratoderivativo")
            or normalized.get("contrato derivativo")
            or normalized.get("contrato")
            or normalized.get("codigo")
            or normalized.get("ticker")
            or ""
        )
        if contract:
            options.append({"value": contract, "label": contract})

    deduped = []
    seen = set()
    for option in options:
        if option["value"] in seen:
            continue
        seen.add(option["value"])
        deduped.append(option)
    return JsonResponse(deduped, safe=False)
