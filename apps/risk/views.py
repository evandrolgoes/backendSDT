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
from apps.tradingview_scraper.services import trigger_contracts_refresh_async

from .models import ExposurePosition
from .serializers import ExposurePositionSerializer


class ExposurePositionViewSet(TenantScopedModelViewSet):
    queryset = ExposurePosition.objects.select_related("tenant", "client", "group", "subgroup", "crop", "season").all()
    serializer_class = ExposurePositionSerializer
    filterset_fields = ["client", "crop", "season", "reference_date"]


def _normalize_text(value):
    return str(value or "").strip().lower()


def _calculate_derivative_mtm(item, quotes_by_ticker=None, usd_brl_rate=0.0):
    """
    Calcula o ajuste MTM de um derivativo usando as mesmas regras do frontend
    (calculateDerivativeMtm / calculatePriceCompositionDerivativeMtm).

    Prioridade do preço de mercado (strike_mercado):
    1. Cotação ao vivo: quotes_by_ticker[item.contrato_derivativo]  ← igual ao frontend
    2. Fallback: item.strike_liquidacao (preço registrado no cadastro)
    3. Se nenhum: usa ajustes_totais armazenados

    Retorna (valor_raw: float, moeda: str "USD" | "BRL" | None).
    """
    import unicodedata

    def normalize_op(value):
        # Mesmo comportamento de normalizeText() no frontend:
        # NFD → remove diacríticos (categoria Mn) → trim → lower
        v = str(value or "").strip()
        v = unicodedata.normalize("NFD", v)
        v = "".join(c for c in v if unicodedata.category(c) != "Mn")
        return v.strip().lower()

    if quotes_by_ticker is None:
        quotes_by_ticker = {}

    status = str(item.status_operacao or "").strip().lower()
    is_usd_op = str(item.volume_financeiro_moeda or "").strip() == "U$"

    # ── Operação encerrada: valores já registrados ──────────────────────────
    if status != "em aberto":
        if item.ajustes_totais_usd is not None:
            return float(item.ajustes_totais_usd), "USD"
        if item.ajustes_totais_brl is not None:
            return float(item.ajustes_totais_brl), "BRL"
        return 0.0, None

    # ── Resolve preço de mercado: cotação ao vivo → strike_liquidacao ──────
    ticker = str(item.contrato_derivativo or "").strip()
    live_price = quotes_by_ticker.get(ticker)
    if live_price is not None:
        strike_mercado_raw = float(live_price)
    elif item.strike_liquidacao:
        strike_mercado_raw = float(item.strike_liquidacao)
    else:
        # Sem preço de mercado → usa ajustes armazenados como estimativa
        if item.ajustes_totais_usd is not None:
            return float(item.ajustes_totais_usd), "USD"
        if item.ajustes_totais_brl is not None:
            return float(item.ajustes_totais_brl), "BRL"
        return 0.0, None

    # ── Resolve nome da operação (igual a resolveDerivativeOperationName) ──
    explicit_name = str(item.nome_da_operacao or "").strip()
    if explicit_name:
        operation_name = normalize_op(explicit_name)
    else:
        posicao = str(item.posicao or "").strip()
        tipo = str(item.tipo_derivativo or "").strip()
        operation_name = normalize_op(f"{posicao} {tipo}".strip())

    # ── Resolve volume (igual a resolveDerivativeVolume) ───────────────────
    mode = str(item.moeda_ou_cmdtye or "").strip().lower()
    if mode == "moeda":
        volume = float(item.volume_financeiro_valor or 0)
    else:
        volume = float(item.volume_fisico_valor or item.numero_lotes or 0)

    # ── Strike factor: centavos → unidade ──────────────────────────────────
    strike_unit = str(item.strike_moeda_unidade or "").strip().lower()
    strike_factor = 0.01 if strike_unit.startswith("c") else 1

    strike_montagem = float(item.strike_montagem or 0) * strike_factor
    strike_mercado = strike_mercado_raw * strike_factor

    # ── Fórmula por tipo de operação (idêntica ao frontend) ────────────────
    usd = 0.0
    if "venda ndf" in operation_name:
        usd = (strike_montagem - strike_mercado) * volume
    elif "compra ndf" in operation_name:
        usd = (strike_mercado - strike_montagem) * volume
    elif "compra call" in operation_name:
        usd = (strike_mercado - strike_montagem) * volume if strike_mercado > strike_montagem else 0.0
    elif "compra put" in operation_name:
        usd = (strike_montagem - strike_mercado) * volume if strike_mercado < strike_montagem else 0.0
    elif "venda call" in operation_name:
        usd = (strike_montagem - strike_mercado) * volume if strike_mercado > strike_montagem else 0.0
    elif "venda put" in operation_name:
        usd = (strike_mercado - strike_montagem) * volume if strike_mercado < strike_montagem else 0.0

    # ── Moeda de retorno ───────────────────────────────────────────────────
    if is_usd_op:
        return usd, "USD"
    else:
        return usd, "BRL"


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


def _format_exchange_summary_label(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("_", " ").replace("-", " ").replace("/", " ")
    return " ".join(part.capitalize() for part in normalized.split())


def _capitalize_first_summary_label(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw[:1].upper() + raw[1:]


def _format_operation_summary_part(value):
    raw = str(value or "").replace("_", " ").replace("-", " ").strip()
    if not raw:
        return ""

    special_tokens = {
        "ndf": "NDF",
        "usd": "USD",
        "brl": "BRL",
    }
    return " ".join(
        special_tokens.get(part.lower(), part[:1].upper() + part[1:].lower())
        for part in raw.split()
    )


def _build_derivative_position_type_summary_label(item):
    parts = [
        _format_operation_summary_part(getattr(item, "posicao", "")),
        _format_operation_summary_part(getattr(item, "tipo_derivativo", "")),
    ]
    operation_label = " ".join(part for part in parts if part).strip()
    return operation_label or _capitalize_first_summary_label(
        item.nome_da_operacao or item.contrato_derivativo or item.cod_operacao_mae or "Operacao derivativa"
    )


def _format_strike_montagem_summary_label(value, unit):
    if value is None or value == "":
        return ""
    formatted = f"{_to_number(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    unit_label = str(unit or "").strip()
    return f"{formatted} {unit_label}".strip()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commercial_risk_summary(request):
    user = request.user

    trigger_contracts_refresh_async(max_age_minutes=5)

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

    # Janela de "Próximos vencimentos" — calculada aqui para empurrar o filtro
    # de data para o nível do queryset e evitar carregar tabelas inteiras só
    # para descartar a maior parte em Python.
    from django.utils import timezone
    from datetime import datetime, timedelta

    today_param = request.query_params.get("today")
    today_date = timezone.localdate()
    if today_param:
        try:
            today_date = datetime.strptime(today_param, "%Y-%m-%d").date()
        except ValueError:
            pass
    cutoff_date = today_date + timedelta(days=90)
    upcoming_window = (today_date, cutoff_date)

    upcoming_physical_sales = list(
        _apply_common_dashboard_filters(
            _scope_queryset(
                PhysicalSale.objects.select_related("grupo", "subgrupo", "cultura", "safra"),
                user,
                group_fields=("grupo",),
                subgroup_fields=("subgrupo",),
            ),
            request,
            group_fields=("grupo",),
            subgroup_fields=("subgrupo",),
        ).filter(data_pagamento__range=upcoming_window)
    )

    upcoming_physical_payments = list(
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
        ).filter(data_pagamento__range=upcoming_window)
    )

    upcoming_cash_payments = list(
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
        ).filter(
            Q(data_pagamento__range=upcoming_window)
            | (Q(data_pagamento__isnull=True) & Q(data_vencimento__range=upcoming_window))
        )
    )

    upcoming_derivatives = list(
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
        ).filter(data_liquidacao__range=upcoming_window)
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

    # Dict ticker → price usado no cálculo MTM (igual ao frontend: derivativeQuotes[row.contrato_derivativo])
    live_quotes_by_ticker = {
        str(q.ticker).strip(): float(q.price)
        for q in market_quotes_rows
        if q.ticker and q.price is not None
    }
    # Taxa USD/BRL ao vivo (ticker USDBRL ou USD/BRL)
    live_usd_brl_rate = (
        live_quotes_by_ticker.get("USDBRL")
        or live_quotes_by_ticker.get("USD/BRL")
        or 0.0
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

    def _build_value_label(value, unit_label="", signed=False):
        amount = _to_number(value)
        unit = str(unit_label or "").strip()
        sign = ("+" if amount >= 0 else "") if signed else ""
        if not signed and not amount:
            return unit or "—"
        def fmt(symbol, val):
            formatted = f"{abs(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if signed:
                prefix = "+" if val >= 0 else "-"
                return f"{prefix} {symbol} {formatted}"
            return f"{symbol} {formatted}"
        if "u$" in _normalize_text(unit) or "usd" in _normalize_text(unit):
            return fmt("U$", amount)
        if "€" in _normalize_text(unit) or "eur" in _normalize_text(unit):
            return fmt("€", amount)
        if "r$" in _normalize_text(unit) or "brl" in _normalize_text(unit):
            return fmt("R$", amount)
        if signed:
            sign = "+" if amount >= 0 else "-"
            formatted = f"{abs(amount):,.0f}".replace(",", ".")
            return f"{sign} {formatted}" + (f" {unit}" if unit else "")
        return f"{amount:,.0f}".replace(",", ".") + (f" {unit}" if unit else "")

    upcoming_rows = []

    for item in upcoming_physical_sales:
        if not item.data_pagamento or item.data_pagamento < today_date or item.data_pagamento > cutoff_date:
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
                "valueColor": "positive",
            }
        )

    for item in upcoming_physical_payments:
        if not item.data_pagamento or item.data_pagamento < today_date or item.data_pagamento > cutoff_date:
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
                "valueLabel": _build_value_label(-abs(_to_number(item.volume)), item.unidade, signed=True),
                "valueColor": "negative",
            }
        )

    for item in upcoming_cash_payments:
        cashflow_date = item.data_pagamento or item.data_vencimento
        if not cashflow_date or cashflow_date < today_date or cashflow_date > cutoff_date:
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
                "valueLabel": _build_value_label(-abs(_to_number(item.valor or item.volume)), item.moeda, signed=True),
                "valueColor": "negative",
            }
        )

    for item in upcoming_derivatives:
        if not item.data_liquidacao or item.data_liquidacao < today_date or item.data_liquidacao > cutoff_date:
            continue
        operation_label = _build_derivative_position_type_summary_label(item)
        exchange_label = _format_exchange_summary_label(item.bolsa_ref)
        strike_label = _format_strike_montagem_summary_label(item.strike_montagem, item.strike_moeda_unidade)
        operation_with_strike = f"{operation_label} {strike_label}".strip()
        derivative_summary_label = (
            f"{exchange_label} - {operation_with_strike}"
            if exchange_label
            else operation_with_strike
        )
        # Ajuste MTM: mesma lógica do frontend — cotação ao vivo via TradingView para operações em aberto
        ajuste_raw, ajuste_moeda = _calculate_derivative_mtm(item, live_quotes_by_ticker, live_usd_brl_rate)
        ajuste_label = _build_value_label(ajuste_raw, ajuste_moeda, signed=True) if ajuste_moeda else "— 0,00"
        upcoming_rows.append(
            {
                "recordId": item.id,
                "resourceKey": "derivative-operations",
                "app": "Derivativos",
                "title": operation_label,
                "summaryLabel": derivative_summary_label,
                "exchangeLabel": exchange_label,
                "strikeMontagemLabel": strike_label,
                "dateLabel": "Liquidacao",
                "dateText": item.data_liquidacao.strftime("%d/%m/%Y"),
                "dateKey": item.data_liquidacao.isoformat(),
                "valueLabel": ajuste_label,
                "valueColor": "positive" if ajuste_raw >= 0 else "negative",
            }
        )

    upcoming_rows.sort(key=lambda item: item["dateKey"])

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
