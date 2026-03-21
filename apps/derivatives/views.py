import json
from decimal import Decimal, InvalidOperation
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import urlopen

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import JsonResponse
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import parsers, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auditing.models import Attachment
from apps.auditing.serializers import AttachmentSerializer
from apps.catalog.models import Crop
from apps.clients.models import Counterparty, CropSeason, EconomicGroup, SubGroup
from apps.core.viewsets import TenantScopedModelViewSet

from .models import DerivativeOperation
from .serializers import DerivativeOperationSerializer


TARGET_FIELD_OPTIONS = [
    {"value": "ignore", "label": "Ignorar"},
    {"value": "cod_operacao_mae", "label": "Cod. operacao mae"},
    {"value": "grupo", "label": "Grupo"},
    {"value": "subgrupo", "label": "Subgrupo"},
    {"value": "cultura", "label": "Cultura"},
    {"value": "destino_cultura", "label": "Cultura destino"},
    {"value": "safra", "label": "Safra"},
    {"value": "bolsa_ref", "label": "Bolsa ref"},
    {"value": "status_operacao", "label": "Status"},
    {"value": "contraparte", "label": "Contraparte"},
    {"value": "data_contratacao", "label": "Data contratacao"},
    {"value": "data_liquidacao", "label": "Data liquidacao"},
    {"value": "contrato_derivativo", "label": "Contrato derivativo"},
    {"value": "dolar_ptax_vencimento", "label": "PTAX"},
    {"value": "moeda_ou_cmdtye", "label": "Moeda ou cmdtye"},
    {"value": "moeda_unidade", "label": "Moeda/unidade"},
    {"value": "nome_da_operacao", "label": "Nome da operacao"},
    {"value": "unidade", "label": "Unidade"},
    {"value": "tipo_derivativo", "label": "Tipo derivativo"},
    {"value": "numero_lotes", "label": "Numero de lotes"},
    {"value": "strike_montagem", "label": "Strike montagem"},
    {"value": "custo_total_montagem_brl", "label": "Custo total montagem"},
    {"value": "strike_liquidacao", "label": "Strike liquidacao"},
    {"value": "ajustes_totais_brl", "label": "Ajustes totais BRL"},
    {"value": "ajustes_totais_usd", "label": "Ajustes totais moeda original"},
    {"value": "volume_financeiro_moeda", "label": "Volume financeiro moeda"},
    {"value": "volume_financeiro_valor_moeda_original", "label": "Volume financeiro valor moeda original"},
    {"value": "volume", "label": "Volume"},
]

SOURCE_FIELD_ALIASES = {
    "cod_operacao_mae": ["codoperacaomae", "_id", "id"],
    "grupo": ["grupo"],
    "subgrupo": ["subgrupo"],
    "cultura": ["culturaproduto"],
    "destino_cultura": ["seformoedadestinodamoeda"],
    "safra": ["safra"],
    "bolsa_ref": ["bolsaref"],
    "status_operacao": ["status"],
    "contraparte": ["contraparteinstituicao"],
    "data_contratacao": ["datacontratacao"],
    "data_liquidacao": ["dataliquidacao"],
    "contrato_derivativo": ["contratoderivativo"],
    "dolar_ptax_vencimento": ["liquidacaodolarptax"],
    "moeda_ou_cmdtye": ["moedacmdtye"],
    "moeda_unidade": ["moedaunidade"],
    "nome_da_operacao": ["nomedaoperacao"],
    "unidade": ["unidade"],
    "tipo_derivativo": ["tipoddoerivativo", "tipoderivativo"],
    "numero_lotes": ["numerodecontratoslotes"],
    "strike_montagem": ["strikemontagem"],
    "custo_total_montagem_brl": ["custototalmontagem"],
    "strike_liquidacao": ["strikeliquidacao"],
    "ajustes_totais_brl": ["liquidacaoajustetotalr"],
    "ajustes_totais_usd": ["liquidacaoajustetotalmoedaoriginal"],
    "volume_financeiro_moeda": ["volumefinanceiromoeda"],
    "volume_financeiro_valor_moeda_original": ["volumefinanceirovalormoedaoriginal"],
    "volume": ["volumefisico"],
}


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


def _normalize_import_key(value):
    return str(value or "").strip()


def _normalize_source_field(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
        .replace("(", "")
        .replace(")", "")
        .replace(":", "")
    )


def _is_local_import_enabled():
    return settings.DEBUG


def _fetch_json_payload(url):
    with urlopen(url, timeout=20) as response:
        return json.load(response)


def _extract_results_and_meta(payload):
    if isinstance(payload, dict) and isinstance(payload.get("response"), dict):
        response = payload["response"]
        return response.get("results", []), response
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return payload.get("results", []), payload
    if isinstance(payload, list):
        return payload, {}
    return [], {}


def _parse_supplied_payload(raw_json):
    if not str(raw_json or "").strip():
        return None
    return json.loads(raw_json)


def _set_url_cursor(url, cursor):
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["cursor"] = str(cursor)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _fetch_all_rows(url):
    rows = []
    next_url = url
    page_guard = 0

    while next_url and page_guard < 100:
        payload = _fetch_json_payload(next_url)
        current_rows, meta = _extract_results_and_meta(payload)
        rows.extend(current_rows if isinstance(current_rows, list) else [])

        remaining = int(meta.get("remaining") or 0)
        count = int(meta.get("count") or len(current_rows) or 0)
        cursor = int(meta.get("cursor") or 0)
        if remaining <= 0 or count <= 0:
            break

        next_url = _set_url_cursor(url, cursor + count)
        page_guard += 1

    return rows


def _suggest_target_field(source_name):
    normalized = _normalize_source_field(source_name)
    for target_field, aliases in SOURCE_FIELD_ALIASES.items():
        if normalized in aliases:
            return target_field
    return "ignore"


def _build_source_field_summary(rows):
    field_names = []
    for row in rows[:25]:
        if isinstance(row, dict):
            for key in row.keys():
                if key not in field_names:
                    field_names.append(key)

    summary = []
    for field_name in field_names:
        sample = ""
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = row.get(field_name)
            if value in (None, "", []):
                continue
            sample = value
            break
        summary.append(
            {
                "sourceField": field_name,
                "sampleValue": sample,
                "suggestedTargetField": _suggest_target_field(field_name),
            }
        )
    return summary


def _parse_decimal(value):
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _parse_date_value(value):
    if value in (None, ""):
        return None
    parsed = parse_datetime(str(value))
    if parsed is not None:
        return parsed.date()
    return parse_date(str(value))


def _lookup_group(tenant, value):
    raw = _normalize_import_key(value)
    if not raw:
        return None
    if raw.isdigit():
        return EconomicGroup.objects.filter(tenant=tenant, pk=int(raw)).first()
    return EconomicGroup.objects.filter(tenant=tenant, grupo__iexact=raw).first()


def _lookup_subgroup(tenant, value):
    raw = _normalize_import_key(value)
    if not raw:
        return None
    if raw.isdigit():
        return SubGroup.objects.filter(tenant=tenant, pk=int(raw)).first()
    return SubGroup.objects.filter(tenant=tenant, subgrupo__iexact=raw).first()


def _lookup_crop(value):
    raw = _normalize_import_key(value)
    if not raw:
        return None
    return Crop.objects.filter(cultura__iexact=raw).first()


def _lookup_season(tenant, value):
    raw = _normalize_import_key(value)
    if not raw:
        return None
    return CropSeason.objects.filter(tenant=tenant, safra__iexact=raw).first()


def _lookup_counterparty(tenant, value):
    raw = _normalize_import_key(value)
    if not raw:
        return None
    return Counterparty.objects.filter(
        tenant=tenant
    ).filter(
        Q(grupo__grupo__iexact=raw) | Q(subgrupo__subgrupo__iexact=raw)
    ).first()


def _apply_mapped_value(instance, target_field, raw_value, tenant, warnings):
    if target_field == "ignore":
        return

    if target_field == "grupo":
        resolved = _lookup_group(tenant, raw_value)
        if resolved is None and raw_value not in (None, ""):
            warnings.append(f"Grupo nao encontrado: {raw_value}")
        instance.grupo = resolved
        return

    if target_field == "subgrupo":
        resolved = _lookup_subgroup(tenant, raw_value)
        if resolved is None and raw_value not in (None, ""):
            warnings.append(f"Subgrupo nao encontrado: {raw_value}")
        instance.subgrupo = resolved
        return

    if target_field == "cultura":
        resolved = _lookup_crop(raw_value)
        if resolved is None and raw_value not in (None, ""):
            warnings.append(f"Cultura nao encontrada: {raw_value}")
        instance.cultura = resolved
        return

    if target_field == "destino_cultura":
        resolved = _lookup_crop(raw_value)
        if resolved is None and raw_value not in (None, ""):
            warnings.append(f"Cultura destino nao encontrada: {raw_value}")
        instance.destino_cultura = resolved
        return

    if target_field == "safra":
        resolved = _lookup_season(tenant, raw_value)
        if resolved is None and raw_value not in (None, ""):
            warnings.append(f"Safra nao encontrada: {raw_value}")
        instance.safra = resolved
        return

    if target_field == "contraparte":
        resolved = _lookup_counterparty(tenant, raw_value)
        if resolved is None and raw_value not in (None, ""):
            warnings.append(f"Contraparte nao encontrada: {raw_value}")
        instance.contraparte = resolved
        return

    if target_field in {"data_contratacao", "data_liquidacao"}:
        setattr(instance, target_field, _parse_date_value(raw_value))
        return

    if target_field in {
        "dolar_ptax_vencimento",
        "numero_lotes",
        "strike_montagem",
        "custo_total_montagem_brl",
        "strike_liquidacao",
        "ajustes_totais_brl",
        "ajustes_totais_usd",
        "volume_financeiro_valor_moeda_original",
        "volume",
    }:
        setattr(instance, target_field, _parse_decimal(raw_value))
        return

    setattr(instance, target_field, _normalize_import_key(raw_value))


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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def inspect_bubble_import(request):
    if not _is_local_import_enabled():
        return Response({"detail": "Importacao provisoria disponivel apenas no ambiente local."}, status=status.HTTP_403_FORBIDDEN)

    url = _normalize_import_key(request.data.get("url"))
    raw_json = request.data.get("rawJson")
    if not url and not str(raw_json or "").strip():
        return Response({"detail": "Informe a URL do JSON ou cole o JSON bruto."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        if str(raw_json or "").strip():
            payload = _parse_supplied_payload(raw_json)
            rows, _meta = _extract_results_and_meta(payload)
        else:
            rows = _fetch_all_rows(url)
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return Response({"detail": "Nao foi possivel ler o JSON informado."}, status=status.HTTP_502_BAD_GATEWAY)

    return Response(
        {
            "databaseTargets": [
                {
                    "value": "local",
                    "label": "Banco local (teste)",
                    "enabled": True,
                }
            ],
            "destinationOptions": [
                {
                    "value": "derivatives",
                    "label": "Derivativos",
                    "enabled": True,
                }
            ],
            "targetFields": TARGET_FIELD_OPTIONS,
            "rowsFound": len(rows),
            "urlReturnedEmpty": bool(url and not rows),
            "sourceFields": _build_source_field_summary(rows),
            "sampleRows": rows[:3],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_bubble_derivatives(request):
    if not _is_local_import_enabled():
        return Response({"detail": "Importacao provisoria disponivel apenas no ambiente local."}, status=status.HTTP_403_FORBIDDEN)

    database_target = _normalize_import_key(request.data.get("databaseTarget"))
    destination = _normalize_import_key(request.data.get("destination"))
    url = _normalize_import_key(request.data.get("url"))
    raw_json = request.data.get("rawJson")
    mapping = request.data.get("mapping") or {}

    if database_target != "local":
        return Response({"detail": "Por enquanto a importacao esta liberada apenas para o banco local."}, status=status.HTTP_400_BAD_REQUEST)
    if destination != "derivatives":
        return Response({"detail": "Por enquanto a importacao provisoria suporta apenas derivativos."}, status=status.HTTP_400_BAD_REQUEST)
    if not url and not str(raw_json or "").strip():
        return Response({"detail": "Informe a URL do JSON ou cole o JSON bruto."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(mapping, dict):
        return Response({"detail": "Mapeamento invalido."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        if str(raw_json or "").strip():
            payload = _parse_supplied_payload(raw_json)
            rows, _meta = _extract_results_and_meta(payload)
        else:
            rows = _fetch_all_rows(url)
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return Response({"detail": "Nao foi possivel ler o JSON informado."}, status=status.HTTP_502_BAD_GATEWAY)

    created_count = 0
    updated_count = 0
    skipped_count = 0
    warnings = []

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            skipped_count += 1
            warnings.append(f"Linha {index}: formato invalido.")
            continue

        import_key = _normalize_import_key(row.get("Cod operação mãe") or row.get("Cod operacao mae") or row.get("_id"))
        if not import_key:
            skipped_count += 1
            warnings.append(f"Linha {index}: sem chave de importacao.")
            continue

        instance = DerivativeOperation.objects.filter(tenant=request.user.tenant, cod_operacao_mae=import_key).order_by("id").first()
        is_new = instance is None
        if instance is None:
            instance = DerivativeOperation(tenant=request.user.tenant, created_by=request.user, cod_operacao_mae=import_key)

        row_warnings = []
        for source_field, target_field in mapping.items():
            if target_field == "ignore":
                continue
            raw_value = row.get(source_field)
            _apply_mapped_value(instance, target_field, raw_value, request.user.tenant, row_warnings)

        if not instance.cod_operacao_mae:
            instance.cod_operacao_mae = import_key

        instance.save()
        if is_new:
            created_count += 1
        else:
            updated_count += 1

        for warning in row_warnings[:5]:
            warnings.append(f"Linha {index}: {warning}")

    return Response(
        {
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "warnings": warnings[:100],
            "rowsProcessed": len(rows),
        }
    )
