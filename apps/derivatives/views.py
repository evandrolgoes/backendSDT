import json
import re
from decimal import Decimal, InvalidOperation
from traceback import format_exc
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.http import JsonResponse
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import parsers, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auditing.context import suppress_audit_signals
from apps.auditing.models import Attachment
from apps.auditing.serializers import AttachmentSerializer
from apps.catalog.models import Crop, Currency, DerivativeOperationName, Exchange, PriceUnit, Unit
from apps.clients.models import Broker, Counterparty, CropSeason, EconomicGroup, SubGroup
from apps.core.viewsets import TenantScopedModelViewSet
from apps.physical.models import ActualCost, BudgetCost, CashPayment, PhysicalPayment, PhysicalQuote, PhysicalSale
from apps.strategies.models import CropBoard, HedgePolicy, Strategy, StrategyTrigger

from .models import DerivativeOperation
from .serializers import DerivativeOperationSerializer


SOURCE_FIELD_ALIASES = {
    "cod_operacao_mae": ["codoperacaomae", "_id", "id"],
    "grupo": ["grupo"],
    "subgrupo": ["subgrupo"],
    "ativo": ["ativo", "culturaproduto", "cultura"],
    "destino_cultura": ["seformoedadestinodamoeda"],
    "safra": ["safra"],
    "bolsa_ref": ["bolsaref"],
    "status_operacao": ["status"],
    "contraparte": ["contraparteinstituicao", "contraparte"],
    "data_contratacao": ["datacontratacao"],
    "data_liquidacao": ["dataliquidacao"],
    "contrato_derivativo": ["contratoderivativo"],
    "dolar_ptax_vencimento": ["liquidacaodolarptax"],
    "moeda_ou_cmdtye": ["moedacmdtye"],
    "strike_moeda_unidade": ["strikemoedaunidade", "moedaunidade"],
    "nome_da_operacao": ["nomedaoperacao"],
    "posicao": ["posicao", "grupomontagem"],
    "tipo_derivativo": ["tipoddoerivativo", "tipoderivativo"],
    "numero_lotes": ["numerodecontratoslotes"],
    "strike_montagem": ["strikemontagem"],
    "custo_total_montagem_brl": ["custototalmontagem"],
    "strike_liquidacao": ["strikeliquidacao"],
    "ajustes_totais_brl": ["liquidacaoajustetotalr"],
    "ajustes_totais_usd": ["liquidacaoajustetotalmoedaoriginal"],
    "volume_financeiro_moeda": ["volumefinanceiromoeda"],
    "volume_financeiro_valor": ["volumefinanceirovalor", "volumefinanceirovalormoedaoriginal"],
    "volume_fisico_unidade": ["volumefisicounidade", "unidade"],
    "volume_fisico_valor": ["volumefisico", "volume"],
    "obs": ["obs", "observacao", "observacoes", "observation"],
}

IMPORT_TARGETS = {
    "derivatives": {
        "label": "Derivativos",
        "model": DerivativeOperation,
        "lookup_fields": ["cod_operacao_mae"],
    },
    "physical_quotes": {
        "label": "Cotacoes Fisico",
        "model": PhysicalQuote,
        "lookup_fields": [],
    },
    "budget_costs": {
        "label": "Custo Orcamento",
        "model": BudgetCost,
        "lookup_fields": [],
    },
    "actual_costs": {
        "label": "Custo Realizado",
        "model": ActualCost,
        "lookup_fields": [],
    },
    "physical_sales": {
        "label": "Vendas Fisico",
        "model": PhysicalSale,
        "lookup_fields": [],
    },
    "physical_payments": {
        "label": "Pgtos Fisico",
        "model": PhysicalPayment,
        "lookup_fields": [],
    },
    "cash_payments": {
        "label": "Pgtos Caixa",
        "model": CashPayment,
        "lookup_fields": [],
    },
    "strategies": {
        "label": "Estrategias",
        "model": Strategy,
        "lookup_fields": [],
    },
    "strategy_triggers": {
        "label": "Gatilhos",
        "model": StrategyTrigger,
        "lookup_fields": [],
    },
    "hedge_policies": {
        "label": "Politica de Hedge",
        "model": HedgePolicy,
        "lookup_fields": [],
    },
    "crop_boards": {
        "label": "Quadro Safra",
        "model": CropBoard,
        "lookup_fields": [],
    },
    "groups": {
        "label": "Grupo",
        "model": EconomicGroup,
        "lookup_fields": ["grupo"],
    },
    "subgroups": {
        "label": "Subgrupo",
        "model": SubGroup,
        "lookup_fields": ["subgrupo"],
    },
    "seasons": {
        "label": "Safra",
        "model": CropSeason,
        "lookup_fields": ["safra"],
    },
    "counterparties": {
        "label": "Contrapartes",
        "model": Counterparty,
        "lookup_fields": [],
    },
    "brokers": {
        "label": "Brokers",
        "model": Broker,
        "lookup_fields": ["name"],
    },
    "crops": {
        "label": "Ativo",
        "model": Crop,
        "lookup_fields": ["ativo"],
    },
    "currencies": {
        "label": "Moeda",
        "model": Currency,
        "lookup_fields": ["nome"],
    },
    "units": {
        "label": "Unidade",
        "model": Unit,
        "lookup_fields": ["nome"],
    },
    "price_units": {
        "label": "Moeda/Unidade",
        "model": PriceUnit,
        "lookup_fields": ["nome"],
    },
    "exchanges": {
        "label": "Bolsa",
        "model": Exchange,
        "lookup_fields": ["nome"],
    },
    "derivative_operation_names": {
        "label": "Nome Operacoes Derivativos",
        "model": DerivativeOperationName,
        "lookup_fields": ["nome"],
    },
}

DERIVATIVE_BULK_SELECT_CONFIG = {
    "bolsa_ref": {"type": "select", "resource": "exchanges", "label_key": "nome", "value_key": "nome"},
    "status_operacao": {
        "type": "select",
        "options": [
            {"value": "Em aberto", "label": "Em aberto"},
            {"value": "Encerrado", "label": "Encerrado"},
        ],
    },
    "contrato_derivativo": {"type": "contract"},
    "moeda_ou_cmdtye": {
        "type": "select",
        "options": [
            {"value": "Moeda", "label": "Moeda"},
            {"value": "Cmdtye", "label": "Cmdtye"},
        ],
    },
    "strike_moeda_unidade": {"type": "select", "resource": "price-units", "label_key": "nome", "value_key": "nome"},
    "nome_da_operacao": {
        "type": "select",
        "resource": "derivative-operation-names",
        "label_key": "nome",
        "value_key": "nome",
    },
    "posicao": {
        "type": "select",
        "options": [
            {"value": "Compra", "label": "Compra"},
            {"value": "Venda", "label": "Venda"},
        ],
    },
    "tipo_derivativo": {
        "type": "select",
        "options": [
            {"value": "Call", "label": "Call"},
            {"value": "Put", "label": "Put"},
            {"value": "NDF", "label": "NDF"},
        ],
    },
    "volume_financeiro_moeda": {"type": "select", "resource": "currencies", "label_key": "nome", "value_key": "nome"},
    "volume_fisico_unidade": {"type": "select", "resource": "units", "label_key": "nome", "value_key": "nome"},
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


def _normalize_import_resource_key(value):
    return str(value or "").strip().replace("-", "_")


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

def _parse_import_headers(raw_headers, authorization_header="", cookie_header=""):
    headers = {
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ),
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    if isinstance(raw_headers, dict):
        iterable = raw_headers.items()
    else:
        iterable = []
        if isinstance(raw_headers, str) and raw_headers.strip():
            try:
                parsed = json.loads(raw_headers)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                iterable = parsed.items()

    for key, value in iterable:
        if key and value not in (None, ""):
            headers[str(key).strip()] = str(value).strip()

    if authorization_header:
        headers["Authorization"] = str(authorization_header).strip()
    if cookie_header:
        headers["Cookie"] = str(cookie_header).strip()

    return headers


def _build_import_database_targets():
    return [
        {
            "value": "current",
            "label": "Banco atual desta instancia",
            "enabled": True,
        }
    ]


def _build_import_destination_options():
    return [
        {"value": key, "label": config["label"], "enabled": True}
        for key, config in IMPORT_TARGETS.items()
    ]


def _humanize_field_label(field):
    return str(getattr(field, "verbose_name", field.name) or field.name).replace("_", " ").strip().capitalize()


def _is_importable_field(field):
    if getattr(field, "auto_created", False):
        return False
    if field.name in {"id", "tenant", "created_by", "created_at", "updated_at"}:
        return False
    if not getattr(field, "concrete", False) and not getattr(field, "many_to_many", False):
        return False
    return True


def _build_target_field_options(destination):
    config = IMPORT_TARGETS.get(destination)
    if not config:
        return [{"value": "ignore", "label": "Ignorar"}]

    options = [{"value": "ignore", "label": "Ignorar"}]
    for field in config["model"]._meta.get_fields():
        if not _is_importable_field(field):
            continue
        label = _humanize_field_label(field)
        if getattr(field, "many_to_many", False):
            label = f"{label} (multi)"
        options.append({"value": field.name, "label": label})
    return options


def _get_derivative_bulk_fields():
    fields = []
    for field in DerivativeOperation._meta.get_fields():
        if not _is_importable_field(field):
            continue

        field_type = "text"
        metadata = {
            "name": field.name,
            "label": _humanize_field_label(field),
            "required": True,
        }

        if field.is_relation:
            related_model = getattr(field, "related_model", None)
            metadata.update(
                {
                    "type": "relation",
                    "resource": next(
                        (
                            key
                            for key, config in IMPORT_TARGETS.items()
                            if config.get("model") is related_model
                        ),
                        None,
                    ),
                }
            )

            if related_model is EconomicGroup:
                metadata["label_key"] = "grupo"
            elif related_model is SubGroup:
                metadata["label_key"] = "subgrupo"
            elif related_model is Crop:
                metadata["label_key"] = "ativo"
            elif related_model is CropSeason:
                metadata["label_key"] = "safra"
            elif related_model is Counterparty:
                metadata["label_key"] = "contraparte"
            fields.append(metadata)
            continue

        if isinstance(field, models.DateField):
            field_type = "date"
        elif isinstance(field, models.DecimalField):
            field_type = "number"
        elif isinstance(field, (models.IntegerField, models.BigIntegerField, models.PositiveIntegerField, models.PositiveSmallIntegerField, models.FloatField)):
            field_type = "number"
        elif isinstance(field, models.TextField):
            field_type = "text"

        metadata["type"] = field_type
        metadata.update(DERIVATIVE_BULK_SELECT_CONFIG.get(field.name, {}))
        fields.append(metadata)

    return fields


def _fetch_json_payload(url, headers=None):
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=20) as response:
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


def _fetch_all_rows(url, headers=None):
    rows = []
    next_url = url
    page_guard = 0

    while next_url and page_guard < 100:
        payload = _fetch_json_payload(next_url, headers=headers)
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


def _suggest_target_field_for_destination(source_name, destination):
    normalized = _normalize_source_field(source_name)
    if destination == "derivatives":
        suggestion = _suggest_target_field(source_name)
        if suggestion != "ignore":
            return suggestion

    config = IMPORT_TARGETS.get(destination)
    if not config:
        return "ignore"

    for field in config["model"]._meta.get_fields():
        if not _is_importable_field(field):
            continue
        normalized_field_name = _normalize_source_field(field.name)
        normalized_field_label = _normalize_source_field(_humanize_field_label(field))
        if normalized in {normalized_field_name, normalized_field_label}:
            return field.name
    return "ignore"


def _build_source_field_summary(rows, destination):
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
                "suggestedTargetField": _suggest_target_field_for_destination(field_name, destination),
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


def _parse_datetime_value(value):
    if value in (None, ""):
        return None
    parsed = parse_datetime(str(value))
    if parsed is not None:
        return parsed
    parsed_date = parse_date(str(value))
    if parsed_date is not None:
        return parsed_date
    return None


def _parse_boolean_value(value):
    if value in (None, ""):
        return False
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "sim", "s", "yes", "y", "on"}


def _lookup_group(tenant, value):
    raw = _normalize_import_key(value)
    if not raw:
        return None
    if raw.isdigit():
        existing = EconomicGroup.objects.filter(tenant=tenant, pk=int(raw)).first()
        if existing is not None:
            return existing
    existing = EconomicGroup.objects.filter(tenant=tenant, grupo__iexact=raw).first()
    if existing is not None:
        return existing
    return EconomicGroup.objects.create(tenant=tenant, grupo=raw)


def _lookup_subgroup(tenant, value):
    return _lookup_subgroup_for_group(tenant, value, None)


def _lookup_subgroup_for_group(tenant, value, group):
    raw = _normalize_import_key(value)
    if not raw:
        return None
    if raw.isdigit():
        existing = SubGroup.objects.filter(tenant=tenant, pk=int(raw)).first()
        if existing is not None:
            return existing
    queryset = SubGroup.objects.filter(tenant=tenant, subgrupo__iexact=raw)
    if group is not None:
        existing = queryset.filter(grupo=group).first()
        if existing is not None:
            return existing
    existing = queryset.first()
    if existing is not None:
        return existing
    if group is None:
        return None
    return SubGroup.objects.create(tenant=tenant, grupo=group, subgrupo=raw)


def _lookup_crop(value):
    raw = _normalize_import_key(value)
    if not raw:
        return None
    existing = Crop.objects.filter(ativo__iexact=raw).first()
    if existing is not None:
        return existing
    return Crop.objects.create(ativo=raw)


def _lookup_season(tenant, value):
    raw = _normalize_import_key(value)
    if not raw:
        return None
    existing = CropSeason.objects.filter(tenant=tenant, safra__iexact=raw).first()
    if existing is not None:
        return existing
    return CropSeason.objects.create(tenant=tenant, safra=raw)


def _lookup_counterparty(tenant, value):
    raw = _normalize_import_key(value)
    if not raw:
        return None
    existing = Counterparty.objects.filter(
        tenant=tenant
    ).filter(
        Q(grupo__grupo__iexact=raw) | Q(contraparte__iexact=raw) | Q(obs__iexact=raw)
    ).first()
    if existing is not None:
        return existing
    return Counterparty.objects.create(tenant=tenant, contraparte=raw, obs=raw)


def _lookup_related_instance(model, tenant, value):
    raw = _normalize_import_key(value)
    if not raw:
        return None

    if model is EconomicGroup:
        return _lookup_group(tenant, raw)
    if model is SubGroup:
        return _lookup_subgroup(tenant, raw)
    if model is Crop:
        return _lookup_crop(raw)
    if model is CropSeason:
        return _lookup_season(tenant, raw)
    if model is Counterparty:
        return _lookup_counterparty(tenant, raw)

    queryset = model.objects.all()
    if any(field.name == "tenant" for field in model._meta.fields):
        queryset = queryset.filter(tenant=tenant)

    if raw.isdigit():
        instance = queryset.filter(pk=int(raw)).first()
        if instance is not None:
            return instance

    preferred_fields = [
        "nome",
        "name",
        "grupo",
        "subgrupo",
        "safra",
        "ativo",
        "code",
        "descricao_estrategia",
        "contraparte",
        "obs",
    ]
    model_fields = {field.name for field in model._meta.fields}
    for field_name in preferred_fields:
        if field_name in model_fields:
            instance = queryset.filter(**{f"{field_name}__iexact": raw}).first()
            if instance is not None:
                return instance
            break

    payload = {}
    if "tenant" in model_fields:
        payload["tenant"] = tenant

    if "nome" in model_fields:
        payload["nome"] = raw
    elif "name" in model_fields:
        payload["name"] = raw
    elif "grupo" in model_fields:
        payload["grupo"] = raw
    elif "subgrupo" in model_fields:
        payload["subgrupo"] = raw
    elif "safra" in model_fields:
        payload["safra"] = raw
    elif "ativo" in model_fields:
        payload["ativo"] = raw
    elif "cultura" in model_fields:
        payload["cultura"] = raw
    elif "code" in model_fields:
        payload["code"] = raw
    elif "descricao_estrategia" in model_fields:
        payload["descricao_estrategia"] = raw
    elif "contraparte" in model_fields:
        payload["contraparte"] = raw
    elif "obs" in model_fields:
        payload["obs"] = raw
    else:
        return None

    try:
        return model.objects.create(**payload)
    except Exception:
        return None


def _resolve_resource_backed_import_value(field_name, raw_value, tenant, warnings):
    field_config = DERIVATIVE_BULK_SELECT_CONFIG.get(field_name) or {}
    resource_key = _normalize_import_resource_key(field_config.get("resource"))
    raw = _normalize_import_key(raw_value)
    if not resource_key or not raw:
        return raw

    target_config = IMPORT_TARGETS.get(resource_key)
    if not target_config:
        warnings.append(f"Configuracao de recurso nao encontrada para {field_name}.")
        return raw

    instance = _lookup_related_instance(target_config["model"], tenant, raw)
    if instance is None:
        warnings.append(f"Nao foi possivel criar ou localizar o cadastro relacionado de {field_name}: {raw}")
        return raw

    model_fields = {field.name for field in instance._meta.fields}
    for candidate in [field_config.get("value_key"), field_config.get("label_key"), "nome", "name", "code"]:
        if candidate and candidate in model_fields:
            resolved = getattr(instance, candidate, None)
            if resolved not in (None, ""):
                return resolved

    return raw


def _split_import_values(raw_value):
    if raw_value in (None, ""):
        return []
    if isinstance(raw_value, (list, tuple, set)):
        return [item for item in raw_value if item not in (None, "")]
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if not stripped:
            return []
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [item for item in parsed if item not in (None, "")]
            except json.JSONDecodeError:
                pass
        parts = [item.strip() for item in re.split(r"[;,|]", stripped) if item.strip()]
        return parts or [stripped]
    return [raw_value]


def _apply_generic_field_value(instance, field, raw_value, tenant, warnings, m2m_updates):
    if getattr(field, "many_to_many", False):
        resolved_items = []
        for item in _split_import_values(raw_value):
            resolved = _lookup_related_instance(field.related_model, tenant, item)
            if resolved is None and item not in (None, ""):
                warnings.append(f"{_humanize_field_label(field)} nao encontrado: {item}")
                continue
            if resolved is not None:
                resolved_items.append(resolved)
        m2m_updates[field.name] = resolved_items
        return

    if field.is_relation:
        resolved = _lookup_related_instance(field.related_model, tenant, raw_value)
        if resolved is None and raw_value not in (None, ""):
            warnings.append(f"{_humanize_field_label(field)} nao encontrado: {raw_value}")
        setattr(instance, field.name, resolved)
        return

    if isinstance(field, models.DateTimeField):
        setattr(instance, field.name, _parse_datetime_value(raw_value))
        return

    if isinstance(field, models.DateField):
        setattr(instance, field.name, _parse_date_value(raw_value))
        return

    if isinstance(field, models.DecimalField):
        setattr(instance, field.name, _parse_decimal(raw_value))
        return

    if isinstance(field, (models.IntegerField, models.BigIntegerField, models.PositiveIntegerField, models.PositiveSmallIntegerField)):
        decimal_value = _parse_decimal(raw_value)
        setattr(instance, field.name, int(decimal_value) if decimal_value is not None else None)
        return

    if isinstance(field, (models.FloatField,)):
        decimal_value = _parse_decimal(raw_value)
        setattr(instance, field.name, float(decimal_value) if decimal_value is not None else None)
        return

    if isinstance(field, models.BooleanField):
        setattr(instance, field.name, _parse_boolean_value(raw_value))
        return

    if isinstance(field, models.JSONField):
        if isinstance(raw_value, str):
            stripped = raw_value.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    setattr(instance, field.name, json.loads(stripped))
                    return
                except json.JSONDecodeError:
                    pass
        setattr(instance, field.name, raw_value if raw_value is not None else field.default() if callable(field.default) else field.default)
        return

    setattr(instance, field.name, _normalize_import_key(raw_value))


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
        resolved = _lookup_subgroup_for_group(tenant, raw_value, getattr(instance, "grupo", None))
        if resolved is None and raw_value not in (None, ""):
            warnings.append(f"Subgrupo nao encontrado ou sem grupo pai definido: {raw_value}")
        instance.subgrupo = resolved
        if resolved is not None and getattr(instance, "grupo_id", None) is None:
            instance.grupo = resolved.grupo
        return

    if target_field == "ativo":
        resolved = _lookup_crop(raw_value)
        if resolved is None and raw_value not in (None, ""):
            warnings.append(f"Ativo nao encontrado: {raw_value}")
        instance.ativo = resolved
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
        "volume_financeiro_valor",
        "volume_fisico_valor",
    }:
        setattr(instance, target_field, _parse_decimal(raw_value))
        return

    if DERIVATIVE_BULK_SELECT_CONFIG.get(target_field, {}).get("resource"):
        setattr(instance, target_field, _resolve_resource_backed_import_value(target_field, raw_value, tenant, warnings))
        return

    setattr(instance, target_field, _normalize_import_key(raw_value))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def import_bubble_targets(request):
    return Response(
        {
            "databaseTargets": _build_import_database_targets(),
            "destinationOptions": _build_import_destination_options(),
        }
    )


class DerivativeOperationViewSet(TenantScopedModelViewSet):
    queryset = DerivativeOperation.objects.select_related(
        "tenant", "subgrupo", "grupo", "ativo", "safra", "contraparte", "created_by"
    ).all()
    serializer_class = DerivativeOperationSerializer
    filterset_fields = ["ativo", "safra", "contraparte", "status_operacao"]
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def derivative_contracts(request):
    secao = request.GET.get("secao") or request.GET.get("seção") or request.GET.get("bolsa") or ""
    normalized_secao = _normalize_derivative_lookup_value(secao)
    if not normalized_secao:
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
        secao_value = (
            normalized.get("section_name")
            or normalized.get("secao")
            or normalized.get("seção")
            or normalized.get("section")
            or ""
        )
        if _normalize_derivative_lookup_value(secao_value) != normalized_secao:
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
    raw_json = request.data.get("rawJson")
    destination = _normalize_import_key(request.data.get("destination")) or "derivatives"
    if destination not in IMPORT_TARGETS:
        return Response({"detail": "Tabela de destino invalida."}, status=status.HTTP_400_BAD_REQUEST)
    if not str(raw_json or "").strip():
        return Response({"detail": "Cole o JSON bruto para continuar."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = _parse_supplied_payload(raw_json)
        rows, _meta = _extract_results_and_meta(payload)
    except (ValueError, json.JSONDecodeError):
        return Response({"detail": "Nao foi possivel interpretar o JSON informado."}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "databaseTargets": _build_import_database_targets(),
            "destinationOptions": _build_import_destination_options(),
            "targetFields": _build_target_field_options(destination),
            "rowsFound": len(rows),
            "urlReturnedEmpty": False,
            "sourceFields": _build_source_field_summary(rows, destination),
            "sampleRows": rows[:3],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_bubble_derivatives(request):
    database_target = _normalize_import_key(request.data.get("databaseTarget"))
    destination = _normalize_import_key(request.data.get("destination"))
    raw_json = request.data.get("rawJson")
    target_config = IMPORT_TARGETS.get(destination)
    mapping = request.data.get("mapping") or {}

    if database_target not in {"", "current"}:
        return Response({"detail": "Banco de destino invalido."}, status=status.HTTP_400_BAD_REQUEST)
    if target_config is None:
        return Response({"detail": "Tabela de destino invalida."}, status=status.HTTP_400_BAD_REQUEST)
    if not str(raw_json or "").strip():
        return Response({"detail": "Cole o JSON bruto para continuar."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(mapping, dict):
        return Response({"detail": "Mapeamento invalido."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = _parse_supplied_payload(raw_json)
        rows, _meta = _extract_results_and_meta(payload)
    except (ValueError, json.JSONDecodeError):
        return Response({"detail": "Nao foi possivel interpretar o JSON informado."}, status=status.HTTP_400_BAD_REQUEST)

    created_count = 0
    skipped_count = 0
    warnings = []
    audit_helper = TenantScopedModelViewSet()
    audit_helper.request = request

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            skipped_count += 1
            warnings.append(f"Linha {index}: formato invalido.")
            continue

        model = target_config["model"]
        import_key = ""
        if model is DerivativeOperation:
            import_key = _normalize_import_key(row.get("Cod operação mãe") or row.get("Cod operacao mae") or row.get("_id"))
        if model is DerivativeOperation and not import_key:
            skipped_count += 1
            warnings.append(f"Linha {index}: sem chave de importacao.")
            continue

        instance = model()
        if any(field.name == "tenant" for field in model._meta.fields):
            instance.tenant = request.user.tenant
        if any(field.name == "created_by" for field in model._meta.fields):
            instance.created_by = request.user
        if model is DerivativeOperation and import_key:
            instance.cod_operacao_mae = import_key

        row_warnings = []
        m2m_updates = {}
        for source_field, target_field in mapping.items():
            if target_field == "ignore":
                continue
            raw_value = row.get(source_field)
            try:
                field = model._meta.get_field(target_field)
            except Exception:
                row_warnings.append(f"Campo de destino invalido: {target_field}")
                continue

            if model is DerivativeOperation:
                _apply_mapped_value(instance, target_field, raw_value, request.user.tenant, row_warnings)
            else:
                _apply_generic_field_value(instance, field, raw_value, request.user.tenant, row_warnings, m2m_updates)

        if model is DerivativeOperation and not instance.cod_operacao_mae:
            instance.cod_operacao_mae = import_key

        try:
            with suppress_audit_signals():
                instance.save()
                for field_name, values in m2m_updates.items():
                    getattr(instance, field_name).set(values)

            audit_helper._create_audit_log("criado", instance, before={}, after=audit_helper._serialize_instance_for_log(instance))
            created_count += 1
        except Exception as exc:
            skipped_count += 1
            warnings.append(f"Linha {index}: erro ao salvar registro ({exc}).")
            print(format_exc())
            continue

        for warning in row_warnings[:5]:
            warnings.append(f"Linha {index}: {warning}")

    return Response(
        {
            "created": created_count,
            "skipped": skipped_count,
            "warnings": warnings[:100],
            "rowsProcessed": len(rows),
        }
    )
