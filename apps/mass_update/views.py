from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.views import TenantViewSet, UserViewSet
from apps.auditing.context import suppress_audit_signals
from apps.catalog.views import (
    CropViewSet,
    CurrencyViewSet,
    DerivativeOperationNameViewSet,
    ExchangeViewSet,
    PriceUnitViewSet,
    UnitViewSet,
)
from apps.clients.views import CounterpartyViewSet, CropSeasonViewSet, EconomicGroupViewSet, SubGroupViewSet
from apps.core.viewsets import TenantScopedModelViewSet
from apps.derivatives.views import DerivativeOperationViewSet
from apps.other_cash_outflows.views import OtherCashOutflowViewSet
from apps.other_entries.views import OtherEntryViewSet
from apps.physical.views import (
    ActualCostViewSet,
    BudgetCostViewSet,
    CashPaymentViewSet,
    PhysicalPaymentViewSet,
    PhysicalQuoteViewSet,
    PhysicalSaleViewSet,
)
from apps.strategies.views import CropBoardViewSet, HedgePolicyViewSet, StrategyTriggerViewSet, StrategyViewSet


RESOURCE_REGISTRY = {
    "tenants": {"label": "Tenants", "viewset": TenantViewSet, "module": "sys_tenants", "superuser_only": True},
    "groups": {"label": "Grupo", "viewset": EconomicGroupViewSet, "module": "cad_groups"},
    "subgroups": {"label": "Subgrupo", "viewset": SubGroupViewSet, "module": "cad_subgroups"},
    "crops": {"label": "Ativo", "viewset": CropViewSet, "module": "sys_crops", "superuser_only": True},
    "currencies": {"label": "Moeda", "viewset": CurrencyViewSet, "module": "sys_currencies", "superuser_only": True},
    "units": {"label": "Unidade", "viewset": UnitViewSet, "module": "sys_units", "superuser_only": True},
    "price-units": {"label": "Moeda/Unidade", "viewset": PriceUnitViewSet, "module": "sys_price_units", "superuser_only": True},
    "exchanges": {"label": "Bolsa", "viewset": ExchangeViewSet, "module": "sys_exchanges", "superuser_only": True},
    "derivative-operation-names": {
        "label": "Nome Operacoes Derivativos",
        "viewset": DerivativeOperationNameViewSet,
        "module": "sys_derivative_operation_names",
        "superuser_only": True,
    },
    "seasons": {"label": "Safra", "viewset": CropSeasonViewSet, "module": "sys_seasons", "superuser_only": True},
    "counterparties": {"label": "Contrapartes", "viewset": CounterpartyViewSet, "module": "cad_counterparties"},
    "physical-quotes": {"label": "Cotacoes Fisico", "viewset": PhysicalQuoteViewSet, "module": "ops_physical_quotes"},
    "budget-costs": {"label": "Custo Orcamento", "viewset": BudgetCostViewSet, "module": "ops_budget_costs"},
    "actual-costs": {"label": "Custo Realizado", "viewset": ActualCostViewSet, "module": "ops_actual_costs"},
    "derivative-operations": {"label": "Derivativos", "viewset": DerivativeOperationViewSet, "module": "ops_derivatives"},
    "physical-sales": {"label": "Vendas Fisico", "viewset": PhysicalSaleViewSet, "module": "ops_physical_sales"},
    "physical-payments": {"label": "Pgtos Fisico", "viewset": PhysicalPaymentViewSet, "module": "ops_physical_payments"},
    "cash-payments": {"label": "Empréstimos", "viewset": CashPaymentViewSet, "module": "ops_cash_payments"},
    "other-cash-outflows": {"label": "Outras saídas Caixa", "viewset": OtherCashOutflowViewSet, "module": "ops_other_cash_outflows"},
    "other-entries": {"label": "Outras Entradas Caixa", "viewset": OtherEntryViewSet, "module": "ops_other_entries"},
    "strategies": {"label": "Estrategias", "viewset": StrategyViewSet, "module": "ops_strategies"},
    "strategy-triggers": {"label": "Gatilhos", "viewset": StrategyTriggerViewSet, "module": "ops_triggers"},
    "hedge-policies": {"label": "Politica de Hedge", "viewset": HedgePolicyViewSet, "module": "ops_hedge_policies"},
    "crop-boards": {"label": "Quadro Safra", "viewset": CropBoardViewSet, "module": "ops_crop_boards"},
    "users": {"label": "Usuarios", "viewset": UserViewSet, "module": "sys_users"},
}

MODEL_LABEL_TO_RESOURCE = {}
for resource_name, config in RESOURCE_REGISTRY.items():
    model = getattr(getattr(config["viewset"], "serializer_class", None), "Meta", None)
    if getattr(model, "model", None):
        MODEL_LABEL_TO_RESOURCE[model.model._meta.label] = resource_name


EXCLUDED_UPDATE_FIELDS = {"id", "tenant", "created_at", "updated_at", "created_by", "attachments", "password"}
EXCLUDED_FILTER_FIELDS = {"id", "created_at", "updated_at", "created_by", "attachments", "password"}
EXCLUDED_IMPORT_FIELDS = {"id", "tenant", "created_at", "updated_at", "created_by", "attachments", "password"}

MASS_IMPORT_FIELD_OVERRIDES = {
    "derivative-operations": {
        "bolsa_ref": {"type": "select", "resource": "exchanges", "labelKey": "nome", "valueKey": "nome"},
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
        "strike_moeda_unidade": {"type": "select", "resource": "price-units", "labelKey": "nome", "valueKey": "nome"},
        "nome_da_operacao": {"type": "select", "resource": "derivative-operation-names", "labelKey": "nome", "valueKey": "nome"},
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
        "volume_financeiro_moeda": {"type": "select", "resource": "currencies", "labelKey": "nome", "valueKey": "nome"},
        "volume_fisico_unidade": {"type": "select", "resource": "units", "labelKey": "nome", "valueKey": "nome"},
    }
}


def _ensure_tool_access(request):
    if request.user.is_superuser:
        return
    if getattr(request.user, "has_module_access", lambda *_args: False)("sys_mass_update"):
        return
    raise PermissionDenied("Voce nao possui acesso a ferramenta de alteracao em massa.")


def _user_has_access(user, config):
    if config.get("superuser_only") and not user.is_superuser:
        return False
    module_code = config.get("module")
    if not module_code:
        return True
    return bool(user.is_superuser or getattr(user, "has_module_access", lambda *_args: False)(module_code))


def _get_resource_config(request, resource):
    config = RESOURCE_REGISTRY.get(resource)
    if not config:
        raise serializers.ValidationError({"resource": "Recurso nao suportado para alteracao em massa."})
    if not _user_has_access(request.user, config):
        raise serializers.ValidationError({"resource": "Voce nao possui acesso a este recurso."})
    return config


def _build_viewset(viewset_class, request):
    viewset = viewset_class()
    viewset.request = request
    viewset.action = "list"
    viewset.format_kwarg = None
    viewset.kwargs = {}
    return viewset


def _get_base_queryset(viewset_class, request):
    return _build_viewset(viewset_class, request).get_queryset()


def _get_serializer(viewset_class, request, *args, **kwargs):
    viewset = _build_viewset(viewset_class, request)
    kwargs.setdefault("context", {"request": request})
    return viewset.get_serializer(*args, **kwargs)


def _normalize_filter_value(raw_value):
    if isinstance(raw_value, list):
        return [item for item in raw_value if item not in ("", None)]
    return raw_value


def _normalize_filter_conditions(filters):
    if isinstance(filters, list):
        return filters
    if isinstance(filters, dict):
        return [{"field": field_name, "value": value} for field_name, value in filters.items()]
    return []


def _normalize_text_match(value):
    return str(value or "").strip().casefold()


def _get_relation_candidate_attrs(field_meta, serializer_field):
    candidates = [field_meta.get("labelKey"), field_meta.get("valueKey")]
    queryset = getattr(serializer_field, "queryset", None)
    model = getattr(queryset, "model", None)
    if model is not None:
        for candidate in ("nome", "name", "title", "grupo", "subgrupo", "ativo", "safra", "contraparte", "username", "email", "full_name"):
            try:
                model._meta.get_field(candidate)
                candidates.append(candidate)
            except Exception:
                continue
    unique_candidates = []
    for candidate in candidates:
        if candidate and candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def _coerce_scalar_value(raw_value, serializer_field, field_meta):
    if raw_value in ("", None):
        return raw_value

    if isinstance(serializer_field, serializers.BooleanField):
        normalized = _normalize_text_match(raw_value)
        if normalized in {"true", "1", "sim", "yes"}:
            return True
        if normalized in {"false", "0", "nao", "não", "no"}:
            return False
        return raw_value

    if isinstance(serializer_field, serializers.ChoiceField):
        normalized = _normalize_text_match(raw_value)
        for key, label in serializer_field.choices.items():
            if normalized in {_normalize_text_match(key), _normalize_text_match(label)}:
                return key
        return raw_value

    if isinstance(serializer_field, serializers.PrimaryKeyRelatedField):
        queryset = getattr(serializer_field, "queryset", None)
        if queryset is None:
            return raw_value

        raw_text = str(raw_value).strip()
        if raw_text.isdigit():
            instance = queryset.filter(pk=int(raw_text)).first()
            if instance is not None:
                return instance.pk

        for attr_name in _get_relation_candidate_attrs(field_meta, serializer_field):
            instance = queryset.filter(**{f"{attr_name}__iexact": raw_text}).first()
            if instance is not None:
                return instance.pk
        return raw_value

    return raw_value


def _coerce_field_value(raw_value, serializer_field, field_meta):
    if isinstance(raw_value, list):
        return [
            item
            for item in (_coerce_scalar_value(value, serializer_field, field_meta) for value in raw_value)
            if item not in ("", None)
        ]
    return _coerce_scalar_value(raw_value, serializer_field, field_meta)


def _apply_filters(queryset, filters, filter_field_map, serializer_field_map):
    for item in _normalize_filter_conditions(filters):
        field_name = item.get("field")
        if not field_name or field_name not in filter_field_map:
            continue

        field_meta = filter_field_map[field_name]
        serializer_field = serializer_field_map.get(field_name)
        normalized = _normalize_filter_value(_coerce_field_value(item.get("value"), serializer_field, field_meta))
        if normalized in ("", None, []):
            continue

        lookup = item.get("lookup") or field_meta.get("defaultLookup") or "exact"
        if isinstance(normalized, list):
            queryset = queryset.filter(**{f"{field_name}__in": normalized})
        else:
            queryset = queryset.filter(**{f"{field_name}__{lookup}": normalized} if lookup != "exact" else {field_name: normalized})
    return queryset


def _apply_search(queryset, viewset_class, search_term):
    term = str(search_term or "").strip()
    if not term:
        return queryset
    search_fields = getattr(viewset_class, "search_fields", []) or []
    if not search_fields:
        return queryset
    from django.db.models import Q

    query = Q()
    for field_name in search_fields:
        query |= Q(**{f"{field_name}__icontains": term})
    return queryset.filter(query)


def _apply_update_match_filters(queryset, updates, update_field_map, serializer_field_map):
    for update in updates or []:
        field_name = update.get("field")
        match_current = bool(update.get("matchCurrent"))
        serializer_field = serializer_field_map.get(field_name)
        field_meta = update_field_map.get(field_name, {})
        from_value = _coerce_field_value(update.get("fromValue"), serializer_field, field_meta)
        if not field_name or not match_current:
            continue
        if isinstance(from_value, list):
            values = [item for item in from_value if item not in ("", None)]
            if values:
                queryset = queryset.filter(**{f"{field_name}__in": values})
            continue
        if from_value in ("", None):
            continue
        queryset = queryset.filter(**{field_name: from_value})
    return queryset


def _serialize_preview_value(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value)


def _get_audit_helper(request):
    helper = TenantScopedModelViewSet()
    helper.request = request
    return helper


def _resolve_field_meta(field_name, serializer_field):
    field_type = "text"
    related_resource = None
    options = None
    default_lookup = "icontains"
    label_key = None
    value_key = None

    if isinstance(serializer_field, serializers.BooleanField):
        field_type = "boolean"
        options = [{"value": True, "label": "Sim"}, {"value": False, "label": "Nao"}]
        default_lookup = "exact"
    elif isinstance(serializer_field, serializers.ChoiceField):
        field_type = "select"
        options = [{"value": key, "label": str(value)} for key, value in serializer_field.choices.items()]
        default_lookup = "exact"
    elif isinstance(serializer_field, (serializers.IntegerField, serializers.FloatField, serializers.DecimalField)):
        field_type = "number"
        default_lookup = "exact"
    elif isinstance(serializer_field, serializers.DateField):
        field_type = "date"
        default_lookup = "exact"
    elif isinstance(serializer_field, serializers.DateTimeField):
        field_type = "datetime"
        default_lookup = "exact"
    elif isinstance(serializer_field, serializers.PrimaryKeyRelatedField):
        field_type = "relation"
        queryset = getattr(serializer_field, "queryset", None)
        model = getattr(queryset, "model", None)
        if model is not None:
            related_resource = MODEL_LABEL_TO_RESOURCE.get(model._meta.label)
            if related_resource == "groups":
                label_key = "grupo"
            elif related_resource == "subgroups":
                label_key = "subgrupo"
            elif related_resource == "crops":
                label_key = "ativo"
            elif related_resource == "seasons":
                label_key = "safra"
            elif related_resource == "counterparties":
                label_key = "contraparte"
        default_lookup = "exact"
    elif isinstance(serializer_field, serializers.ManyRelatedField):
        field_type = "multirelation"
        child_relation = getattr(serializer_field, "child_relation", None)
        queryset = getattr(child_relation, "queryset", None)
        model = getattr(queryset, "model", None)
        if model is not None:
            related_resource = MODEL_LABEL_TO_RESOURCE.get(model._meta.label)
            if related_resource == "groups":
                label_key = "grupo"
            elif related_resource == "subgroups":
                label_key = "subgrupo"
            elif related_resource == "crops":
                label_key = "ativo"
            elif related_resource == "seasons":
                label_key = "safra"
            elif related_resource == "counterparties":
                label_key = "contraparte"
        default_lookup = "in"
    elif isinstance(serializer_field, serializers.ListField):
        field_type = "list"

    return {
        "name": field_name,
        "label": serializer_field.label or field_name.replace("_", " ").title(),
        "type": field_type,
        "required": serializer_field.required,
        "allowNull": getattr(serializer_field, "allow_null", False),
        "relatedResource": related_resource,
        "labelKey": label_key,
        "valueKey": value_key,
        "options": options,
        "defaultLookup": default_lookup,
    }


def _build_resource_metadata(resource, config, request):
    serializer = _get_serializer(config["viewset"], request)
    fields = serializer.fields
    update_fields = []
    filter_fields = []

    for field_name, serializer_field in fields.items():
        if isinstance(serializer_field, serializers.HiddenField):
            continue

        meta = _resolve_field_meta(field_name, serializer_field)

        if not serializer_field.write_only and field_name not in EXCLUDED_FILTER_FIELDS and meta["type"] not in {"list", "multirelation"}:
            filter_fields.append(meta)

        if serializer_field.read_only or serializer_field.write_only:
            continue
        if field_name in EXCLUDED_UPDATE_FIELDS:
            continue
        if meta["type"] in {"list", "multirelation"}:
            continue
        update_fields.append(meta)

    return {
        "resource": resource,
        "label": config["label"],
        "filters": filter_fields,
        "updateFields": update_fields,
        "searchEnabled": bool(getattr(config["viewset"], "search_fields", []) or []),
    }


def _build_mass_import_metadata(resource, config, request):
    serializer = _get_serializer(config["viewset"], request)
    fields = []
    overrides = MASS_IMPORT_FIELD_OVERRIDES.get(resource, {})

    for field_name, serializer_field in serializer.fields.items():
        if isinstance(serializer_field, serializers.HiddenField):
            continue
        if serializer_field.read_only or serializer_field.write_only:
            continue
        if field_name in EXCLUDED_IMPORT_FIELDS:
            continue

        meta = _resolve_field_meta(field_name, serializer_field)
        override = overrides.get(field_name, {})
        merged = {
            "name": field_name,
            "label": meta["label"],
            "type": meta["type"],
            "required": False,
            "resource": meta.get("relatedResource"),
            "options": meta.get("options"),
            "labelKey": None,
            "valueKey": None,
        }

        if meta["type"] == "relation":
            related_resource = meta.get("relatedResource")
            if related_resource == "groups":
                merged["labelKey"] = "grupo"
            elif related_resource == "subgroups":
                merged["labelKey"] = "subgrupo"
            elif related_resource == "crops":
                merged["labelKey"] = "ativo"
            elif related_resource == "seasons":
                merged["labelKey"] = "safra"
            elif related_resource == "counterparties":
                merged["labelKey"] = "contraparte"

        merged.update(override)
        fields.append(merged)

    return {
        "resource": resource,
        "label": config["label"],
        "fields": fields,
    }


def _get_filtered_queryset(request, resource, filters, search_term, updates):
    config = _get_resource_config(request, resource)
    queryset = _get_base_queryset(config["viewset"], request)
    metadata = _build_resource_metadata(resource, config, request)
    filter_field_map = {item["name"]: item for item in metadata["filters"]}
    update_field_map = {item["name"]: item for item in metadata["updateFields"]}
    serializer_field_map = _get_serializer(config["viewset"], request).fields
    queryset = _apply_filters(queryset, filters, filter_field_map, serializer_field_map)
    queryset = _apply_search(queryset, config["viewset"], search_term)
    queryset = _apply_update_match_filters(queryset, updates, update_field_map, serializer_field_map)
    return queryset.distinct(), config


def _build_payload(updates, serializer_field_map, update_field_map):
    payload = {}
    for update in updates or []:
        field_name = update.get("field")
        if not field_name:
            continue
        if update.get("clearTarget"):
            payload[field_name] = None
            continue
        serializer_field = serializer_field_map.get(field_name)
        field_meta = update_field_map.get(field_name, {})
        payload[field_name] = _coerce_field_value(update.get("toValue"), serializer_field, field_meta)
    return payload


class MassUpdateResourcesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _ensure_tool_access(request)
        resources = [
            {"value": resource, "label": config["label"], "module": config.get("module")}
            for resource, config in RESOURCE_REGISTRY.items()
            if _user_has_access(request.user, config)
        ]
        return Response({"resources": resources})


class MassImportResourcesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _ensure_tool_access(request)
        resources = [
            {"value": resource, "label": config["label"], "module": config.get("module")}
            for resource, config in RESOURCE_REGISTRY.items()
            if _user_has_access(request.user, config)
        ]
        return Response({"resources": resources})


class MassImportMetadataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _ensure_tool_access(request)
        resource = request.query_params.get("resource")
        config = _get_resource_config(request, resource)
        return Response(_build_mass_import_metadata(resource, config, request))


class MassImportApplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        _ensure_tool_access(request)
        resource = request.data.get("resource")
        rows = request.data.get("rows") or []

        if not isinstance(rows, list) or not rows:
            raise serializers.ValidationError({"rows": "Informe pelo menos uma linha para importar."})

        config = _get_resource_config(request, resource)
        helper = _get_audit_helper(request)
        serializer_class = config["viewset"].serializer_class
        model = serializer_class.Meta.model
        created = []
        row_errors = {}

        with transaction.atomic():
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    row_errors[str(index + 1)] = {"detail": "Linha invalida."}
                    continue

                payload = {key: value for key, value in row.items() if value not in ("", None, [], {})}
                serializer = _get_serializer(config["viewset"], request, data=payload)
                if not serializer.is_valid():
                    row_errors[str(index + 1)] = serializer.errors
                    continue

                extra = {}
                if hasattr(model, "tenant"):
                    if not request.user.tenant_id:
                        raise serializers.ValidationError({"tenant": "O usuario autenticado nao possui tenant vinculado."})
                    extra["tenant"] = request.user.tenant
                if hasattr(model, "created_by"):
                    extra["created_by"] = request.user

                with suppress_audit_signals():
                    instance = serializer.save(**extra)
                helper._create_audit_log("criado", instance, before={}, after=helper._serialize_instance_for_log(instance))
                created.append(instance.pk)

            if row_errors:
                raise serializers.ValidationError({"rows": row_errors, "detail": "Existem linhas invalidas na importacao."})

        return Response(
            {
                "resource": resource,
                "label": config["label"],
                "createdCount": len(created),
                "createdIds": created[:20],
            }
        )


class MassUpdateMetadataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _ensure_tool_access(request)
        resource = request.query_params.get("resource")
        config = _get_resource_config(request, resource)
        return Response(_build_resource_metadata(resource, config, request))


class MassUpdatePreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        _ensure_tool_access(request)
        resource = request.data.get("resource")
        filters = request.data.get("filters") or {}
        updates = request.data.get("updates") or []
        search_term = request.data.get("search") or ""
        queryset, config = _get_filtered_queryset(request, resource, filters, search_term, updates)
        preview_items = list(queryset.values("id")[:5])
        return Response(
            {
                "resource": resource,
                "label": config["label"],
                "affectedCount": queryset.count(),
                "sampleIds": [item["id"] for item in preview_items],
            }
        )


class MassUpdateApplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        _ensure_tool_access(request)
        resource = request.data.get("resource")
        filters = request.data.get("filters") or {}
        updates = request.data.get("updates") or []
        search_term = request.data.get("search") or ""

        if not updates:
            raise serializers.ValidationError({"updates": "Informe pelo menos uma alteracao."})

        queryset, config = _get_filtered_queryset(request, resource, filters, search_term, updates)
        metadata = _build_resource_metadata(resource, config, request)
        update_field_map = {item["name"]: item for item in metadata["updateFields"]}
        serializer_field_map = _get_serializer(config["viewset"], request).fields
        payload = _build_payload(updates, serializer_field_map, update_field_map)
        if not payload:
            raise serializers.ValidationError({"updates": "Nao foi possivel montar as alteracoes solicitadas."})

        helper = _get_audit_helper(request)
        updated_count = 0
        updated_ids = []

        with transaction.atomic():
            for instance in queryset:
                before = helper._serialize_instance_for_log(instance)
                serializer = _get_serializer(config["viewset"], request, instance, data=payload, partial=True)
                serializer.is_valid(raise_exception=True)
                with suppress_audit_signals():
                    updated_instance = serializer.save()
                helper._create_audit_log(
                    "alterado",
                    updated_instance,
                    before=before,
                    after=helper._serialize_instance_for_log(updated_instance),
                )
                updated_count += 1
                if len(updated_ids) < 20:
                    updated_ids.append(updated_instance.pk)

        return Response(
            {
                "resource": resource,
                "label": config["label"],
                "updatedCount": updated_count,
                "updatedIds": updated_ids,
            }
        )
