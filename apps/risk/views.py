from django.db.models import Q
from functools import reduce
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.viewsets import TenantScopedModelViewSet
from apps.derivatives.models import DerivativeOperation
from apps.mercado.models import MarketNewsPost
from apps.mercado.serializers import MarketNewsPostSerializer
from apps.physical.models import BudgetCost, CashPayment, PhysicalPayment, PhysicalQuote, PhysicalSale
from apps.core.privacy import apply_group_privacy_scope
from apps.strategies.models import CropBoard, HedgePolicy
from apps.tradingview_scraper.models import TradingViewWatchlistQuote
from apps.tradingview_scraper.serializers import TradingViewWatchlistQuoteSerializer
from apps.tradingview_scraper.services import trigger_watchlist_refresh_async

from .models import ExposurePosition
from .serializers import ExposurePositionSerializer


class ExposurePositionViewSet(TenantScopedModelViewSet):
    queryset = ExposurePosition.objects.select_related("tenant", "client", "group", "subgroup", "crop", "season").all()
    serializer_class = ExposurePositionSerializer
    filterset_fields = ["client", "crop", "season", "reference_date"]


def _normalize_text(value):
    return str(value or "").strip().lower()


def _parse_multi_value_param(request, key):
    values = []
    raw_items = request.query_params.getlist(key)
    if not raw_items:
        raw_items = request.query_params.getlist(f"{key}[]")
    for item in raw_items:
        if item is None:
            continue
        parts = [part.strip() for part in str(item).split(",")]
        values.extend(part for part in parts if part)
    return values


def _scope_queryset(queryset, user, group_fields=(), subgroup_fields=()):
    return apply_group_privacy_scope(queryset, user, group_fields=group_fields, subgroup_fields=subgroup_fields)


def _apply_common_dashboard_filters(queryset, request, *, group_fields=(), subgroup_fields=(), culture_fields=(), season_fields=()):
    group_ids = _parse_multi_value_param(request, "grupo")
    subgroup_ids = _parse_multi_value_param(request, "subgrupo")
    culture_ids = _parse_multi_value_param(request, "cultura")
    season_ids = _parse_multi_value_param(request, "safra")

    if group_ids and group_fields:
        predicate = Q()
        for field_name in group_fields:
            field = queryset.model._meta.get_field(field_name)
            lookup = f"{field_name}__id__in" if getattr(field, "many_to_many", False) else f"{field_name}_id__in"
            predicate |= Q(**{lookup: group_ids})
        queryset = queryset.filter(predicate)

    if subgroup_ids and subgroup_fields:
        predicate = Q()
        for field_name in subgroup_fields:
            field = queryset.model._meta.get_field(field_name)
            lookup = f"{field_name}__id__in" if getattr(field, "many_to_many", False) else f"{field_name}_id__in"
            predicate |= Q(**{lookup: subgroup_ids})
        queryset = queryset.filter(predicate)

    if culture_ids and culture_fields:
        predicate = Q()
        for field_name in culture_fields:
            field = queryset.model._meta.get_field(field_name)
            lookup = f"{field_name}__id__in" if getattr(field, "many_to_many", False) else f"{field_name}_id__in"
            predicate |= Q(**{lookup: culture_ids})
        queryset = queryset.filter(predicate)

    if season_ids and season_fields:
        predicate = Q()
        for field_name in season_fields:
            field = queryset.model._meta.get_field(field_name)
            lookup = f"{field_name}__id__in" if getattr(field, "many_to_many", False) else f"{field_name}_id__in"
            predicate |= Q(**{lookup: season_ids})
        queryset = queryset.filter(predicate)

    return queryset.distinct()


def _to_number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commercial_risk_summary(request):
    user = request.user

    trigger_watchlist_refresh_async(max_age_minutes=5)

    crop_boards_qs = _apply_common_dashboard_filters(
        _scope_queryset(
            CropBoard.objects.select_related("grupo", "subgrupo", "cultura", "safra"),
            user,
            group_fields=("grupo",),
            subgroup_fields=("subgrupo",),
        ),
        request,
        group_fields=("grupo",),
        subgroup_fields=("subgrupo",),
        culture_fields=("cultura",),
        season_fields=("safra",),
    )
    crop_boards = list(crop_boards_qs)

    physical_sales_qs = _apply_common_dashboard_filters(
        _scope_queryset(
            PhysicalSale.objects.select_related("grupo", "subgrupo", "cultura", "safra"),
            user,
            group_fields=("grupo",),
            subgroup_fields=("subgrupo",),
        ),
        request,
        group_fields=("grupo",),
        subgroup_fields=("subgrupo",),
        culture_fields=("cultura",),
        season_fields=("safra",),
    )
    physical_sales = list(physical_sales_qs)

    physical_payments = list(
        _apply_common_dashboard_filters(
            _scope_queryset(
                PhysicalPayment.objects.select_related("grupo", "subgrupo", "fazer_frente_com", "safra"),
                user,
                group_fields=("grupo",),
                subgroup_fields=("subgrupo",),
            ),
            request,
            group_fields=("grupo",),
            subgroup_fields=("subgrupo",),
            culture_fields=("fazer_frente_com",),
            season_fields=("safra",),
        )
    )

    cash_payments = list(
        _apply_common_dashboard_filters(
            _scope_queryset(
                CashPayment.objects.select_related("grupo", "subgrupo", "fazer_frente_com", "safra"),
                user,
                group_fields=("grupo",),
                subgroup_fields=("subgrupo",),
            ),
            request,
            group_fields=("grupo",),
            subgroup_fields=("subgrupo",),
            culture_fields=("fazer_frente_com",),
            season_fields=("safra",),
        )
    )

    derivatives = list(
        _apply_common_dashboard_filters(
            _scope_queryset(
                DerivativeOperation.objects.select_related("grupo", "subgrupo", "ativo", "destino_cultura", "safra"),
                user,
                group_fields=("grupo",),
                subgroup_fields=("subgrupo",),
            ),
            request,
            group_fields=("grupo",),
            subgroup_fields=("subgrupo",),
            culture_fields=("ativo", "destino_cultura"),
            season_fields=("safra",),
        )
    )

    hedge_policies_count = _apply_common_dashboard_filters(
        _scope_queryset(
            HedgePolicy.objects.select_related("cultura", "safra"),
            user,
            group_fields=("grupos",),
            subgroup_fields=("subgrupos",),
        ),
        request,
        group_fields=("grupos",),
        subgroup_fields=("subgrupos",),
        culture_fields=("cultura",),
        season_fields=("safra",),
    ).count()

    budget_costs_count = _apply_common_dashboard_filters(
        _scope_queryset(
            BudgetCost.objects.select_related("grupo", "subgrupo", "cultura", "safra"),
            user,
            group_fields=("grupo",),
            subgroup_fields=("subgrupo",),
        ),
        request,
        group_fields=("grupo",),
        subgroup_fields=("subgrupo",),
        culture_fields=("cultura",),
        season_fields=("safra",),
    ).count()

    physical_quotes_qs = _apply_common_dashboard_filters(
        _scope_queryset(PhysicalQuote.objects.select_related("safra"), user),
        request,
        season_fields=("safra",),
    )
    physical_quotes = list(physical_quotes_qs)
    physical_quotes_count = len(physical_quotes)

    market_news_qs = _scope_queryset(
        MarketNewsPost.objects.select_related("tenant", "created_by", "published_by"),
        user,
    )
    if not (user.is_superuser or user.is_tenant_admin()):
        market_news_qs = market_news_qs.filter(status_artigo=MarketNewsPost.STATUS_PUBLISHED)
    market_news_rows = list(market_news_qs.order_by("-data_publicacao", "-created_at")[:12])

    market_quotes_rows = list(
        TradingViewWatchlistQuote.objects.all().order_by("sort_order", "ticker")
    )

    production_total = sum(abs(_to_number(item.producao_total)) for item in crop_boards)
    total_area = sum(abs(_to_number(item.area)) for item in crop_boards)
    physical_payment_volume = sum(abs(_to_number(item.volume)) for item in physical_payments)
    net_production_volume = max(production_total - physical_payment_volume, 0)

    forms = [
        {"label": "Quadro Safra", "path": "/quadro-safra", "count": len(crop_boards), "hint": "Base de produção e cobertura"},
        {"label": "Vendas Físico", "path": "/vendas-fisico", "count": len(physical_sales), "hint": "Contratos físicos negociados"},
        {"label": "Derivativos", "path": "/derivativos", "count": len(derivatives), "hint": "Operações em bolsa e câmbio"},
        {"label": "Cotações Físico", "path": "/cotacoes-fisico", "count": physical_quotes_count, "hint": "Referência de mercado / MTM"},
        {"label": "Política de Hedge", "path": "/politica-hedge", "count": hedge_policies_count, "hint": "Faixas e disciplina de risco"},
        {"label": "Custo Orçamento", "path": "/custo-orcamento", "count": budget_costs_count, "hint": "Base de margem e cobertura"},
        {"label": "Pgtos Físico", "path": "/pgtos-fisico", "count": len(physical_payments), "hint": "Fluxo operacional do físico"},
        {"label": "Empréstimos", "path": "/pgtos-caixa", "count": len(cash_payments), "hint": "Saídas financeiras do caixa"},
    ]
    form_completion_rows = [{**item, "status": "Preenchido" if item["count"] > 0 else "Pendente"} for item in forms]
    filled_forms = sum(1 for item in form_completion_rows if item["count"] > 0)
    form_completion_summary = {
        "totalForms": len(form_completion_rows),
        "filledForms": filled_forms,
        "pendingForms": len(form_completion_rows) - filled_forms,
        "totalRecords": sum(item["count"] for item in form_completion_rows),
    }

    def _build_value_label(value, unit_label=""):
        amount = _to_number(value)
        unit = str(unit_label or "").strip()
        if not amount:
            return unit or "—"
        if "u$" in _normalize_text(unit) or "usd" in _normalize_text(unit):
            return f"U$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if "€" in _normalize_text(unit) or "eur" in _normalize_text(unit):
            return f"€ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if "r$" in _normalize_text(unit) or "brl" in _normalize_text(unit):
            return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{amount:,.0f}".replace(",", ".") + (f" {unit}" if unit else "")

    upcoming_rows = []
    today = request.query_params.get("today")

    from django.utils import timezone
    from datetime import datetime

    today_date = timezone.localdate()
    if today:
        try:
            today_date = datetime.strptime(today, "%Y-%m-%d").date()
        except ValueError:
            pass

    for item in physical_sales:
        if not item.data_pagamento or item.data_pagamento < today_date:
            continue
        upcoming_rows.append(
            {
                "recordId": item.id,
                "resourceKey": "physical-sales",
                "app": "Vendas Fisico",
                "title": item.cultura_produto or "Contrato fisico",
                "summaryLabel": item.cultura_produto or "Contrato fisico",
                "dateLabel": "Pagamento",
                "dateText": item.data_pagamento.strftime("%d/%m/%Y"),
                "dateKey": item.data_pagamento.isoformat(),
                "valueLabel": _build_value_label(item.faturamento_total_contrato or (_to_number(item.preco) * _to_number(item.volume_fisico)), item.moeda_contrato),
            }
        )

    for item in physical_payments:
        if not item.data_pagamento or item.data_pagamento < today_date:
            continue
        upcoming_rows.append(
            {
                "recordId": item.id,
                "resourceKey": "physical-payments",
                "app": "Pgtos Fisico",
                "title": item.descricao or "Pagamento fisico",
                "summaryLabel": item.descricao or "Pagamento fisico",
                "dateLabel": "Pagamento",
                "dateText": item.data_pagamento.strftime("%d/%m/%Y"),
                "dateKey": item.data_pagamento.isoformat(),
                "valueLabel": _build_value_label(item.volume, item.unidade),
            }
        )

    for item in cash_payments:
        cashflow_date = item.data_pagamento or item.data_vencimento
        if not cashflow_date or cashflow_date < today_date:
            continue
        upcoming_rows.append(
            {
                "recordId": item.id,
                "resourceKey": "cash-payments",
                "app": "Empréstimos",
                "title": item.descricao or "Pagamento caixa",
                "summaryLabel": item.descricao or "Pagamento caixa",
                "dateLabel": "Pagamento" if item.data_pagamento else "Vencimento",
                "dateText": cashflow_date.strftime("%d/%m/%Y"),
                "dateKey": cashflow_date.isoformat(),
                "valueLabel": _build_value_label(item.valor or item.volume, item.moeda),
            }
        )

    for item in derivatives:
        if not item.data_liquidacao or item.data_liquidacao < today_date:
            continue
        operation_label = item.nome_da_operacao or item.contrato_derivativo or item.cod_operacao_mae or "Operacao derivativa"
        upcoming_rows.append(
            {
                "recordId": item.id,
                "resourceKey": "derivative-operations",
                "app": "Derivativos",
                "title": operation_label,
                "summaryLabel": operation_label,
                "dateLabel": "Liquidacao",
                "dateText": item.data_liquidacao.strftime("%d/%m/%Y"),
                "dateKey": item.data_liquidacao.isoformat(),
                "valueLabel": _build_value_label(
                    item.volume_financeiro_valor or item.volume_fisico_valor or item.numero_lotes,
                    item.volume_financeiro_moeda or item.volume_fisico_unidade or item.strike_moeda_unidade,
                ),
            }
        )

    upcoming_rows.sort(key=lambda item: item["dateKey"])
    upcoming_rows = upcoming_rows[:8]

    return Response(
        {
            "productionSummary": {
                "productionTotal": production_total,
                "totalArea": total_area,
                "physicalPaymentVolume": physical_payment_volume,
                "netProductionVolume": net_production_volume,
            },
            "marketQuotes": TradingViewWatchlistQuoteSerializer(market_quotes_rows, many=True).data,
            "marketNewsPosts": MarketNewsPostSerializer(market_news_rows, many=True).data,
            "upcomingMaturityRows": upcoming_rows,
            "formCompletionRows": form_completion_rows,
            "formCompletionSummary": form_completion_summary,
        }
    )
