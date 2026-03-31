import json
from collections import defaultdict
from datetime import timedelta
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.derivatives.models import DerivativeOperation
from apps.mercado.models import MarketNewsPost
from apps.physical.models import BudgetCost, CashPayment, PhysicalPayment, PhysicalSale
from apps.strategies.models import CropBoard, HedgePolicy


def _normalize_text(value):
    return str(value or "").strip().lower()


def _normalize_locality(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        parts = [value.get("uf") or value.get("sigla") or "", value.get("cidade") or value.get("nome") or ""]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        parts = str(value).split("/")
    normalized_parts = [_normalize_text(part) for part in parts if str(part or "").strip()]
    return "|".join(sorted(normalized_parts))


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


def _to_number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_policy_ratio(value):
    parsed = _to_number(value)
    if not parsed:
        return None
    return parsed / 100 if parsed > 1.5 else parsed


def _scope_queryset(queryset, user, group_fields=(), subgroup_fields=()):
    if user.is_superuser:
        return queryset

    accessible_tenant_ids = getattr(user, "get_accessible_tenant_ids", lambda: [getattr(user, "tenant_id", None)])()
    if hasattr(queryset.model, "tenant_id"):
        queryset = queryset.filter(tenant_id__in=accessible_tenant_ids)

    return queryset.distinct()


def _apply_filters(queryset, request, *, group_fields=(), subgroup_fields=(), culture_fields=(), season_fields=()):
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


def _filter_locality_rows(rows, selected_localities, getter):
    if not selected_localities:
        return rows
    selected = {_normalize_locality(item) for item in selected_localities if _normalize_locality(item)}
    filtered = []
    for row in rows:
        row_values = getter(row)
        if any(_normalize_locality(value) in selected for value in row_values):
            filtered.append(row)
    return filtered


def _read_label(value, fallback="Sem ativo"):
    if value is None or value == "":
        return fallback
    if isinstance(value, str):
        return value
    return (
        getattr(value, "ativo", None)
        or getattr(value, "cultura", None)
        or getattr(value, "nome", None)
        or getattr(value, "label", None)
        or str(value)
    )


def _get_derivative_exchange_factor(item):
    bolsa = _normalize_text(item.bolsa_ref)
    if not bolsa:
        return 1
    from apps.catalog.models import Exchange

    exchange = Exchange.objects.filter(nome__iexact=item.bolsa_ref).first()
    factor = _to_number(getattr(exchange, "fator_conversao_unidade_padrao_cultura", 0))
    return factor if factor > 0 else 1


def _get_derivative_standard_volume(item):
    base_volume = abs(
        _to_number(item.volume_fisico_valor)
        or _to_number(getattr(item, "volume_fisico", 0))
        or _to_number(getattr(item, "volume", 0))
        or _to_number(item.numero_lotes)
    )
    if not base_volume:
        return 0
    return base_volume / _get_derivative_exchange_factor(item)


def _format_pct(value):
    return round((value or 0) * 100, 1)


def _format_sc(value):
    return f"{round(value or 0):,}".replace(",", ".") + " sc"


def _format_brl(value):
    return "R$ " + f"{round(value or 0):,}".replace(",", ".")


def _start_of_month(value):
    if not value:
        return None
    return value.replace(day=1)


def _select_active_policy_for_reference_date(policies, reference_date):
    policy_rows = []
    for item in policies or []:
        month_date = _start_of_month(getattr(item, "mes_ano", None))
        min_ratio = _normalize_policy_ratio(getattr(item, "vendas_x_prod_total_minimo", None))
        max_ratio = _normalize_policy_ratio(getattr(item, "vendas_x_prod_total_maximo", None))
        if month_date and (min_ratio is not None or max_ratio is not None):
            policy_rows.append(
                {
                    "instance": item,
                    "month_date": month_date,
                    "min_ratio": min_ratio,
                    "max_ratio": max_ratio,
                }
            )

    if not policy_rows:
        return None

    policy_rows.sort(key=lambda item: item["month_date"])
    reference_month = _start_of_month(reference_date)
    active_policy = policy_rows[0]
    for item in policy_rows[1:]:
        if item["month_date"] <= reference_month:
            active_policy = item
            continue
        break
    return active_policy


def _build_local_insights(payload):
    metrics = payload["metrics"]
    coverage = metrics["commercialization_coverage_ratio"]
    policy_min = metrics["policy_min_ratio"]
    policy_max = metrics["policy_max_ratio"]
    uncovered_volume = metrics["uncovered_volume_sc"]
    over_hedged_volume = metrics["over_hedged_volume_sc"]
    budget_cost_total = metrics["budget_cost_total_brl"]
    news_count = payload["context"]["recent_news_count"]

    status = "sem_politica"
    if policy_min is not None and policy_max is not None:
        if coverage < policy_min:
            status = "abaixo"
        elif coverage > policy_max:
            status = "acima"
        else:
            status = "dentro"

    action = "monitorar"
    if status == "abaixo" and uncovered_volume > 0:
        action = "vender"
    elif status == "acima" and over_hedged_volume > 0:
        action = "segurar"

    executive_summary = []
    if status == "abaixo":
        executive_summary.append(
            f"A cobertura comercial está abaixo da política de hedge e ainda existem aproximadamente {round(uncovered_volume):,.0f} sc sem proteção."
        )
    elif status == "acima":
        executive_summary.append(
            f"A cobertura comercial está acima da política de hedge em aproximadamente {round(over_hedged_volume):,.0f} sc."
        )
    elif status == "dentro":
        executive_summary.append("A cobertura comercial está dentro da faixa prevista pela política de hedge.")
    else:
        executive_summary.append("Não foi encontrada política de hedge ativa para comparar a posição comercial atual.")

    if metrics["net_production_sc"] > 0:
        executive_summary.append(
            f"A produção líquida considerada é de {round(metrics['net_production_sc']):,.0f} sc e o volume já comercializado/protegido soma {round(metrics['commercialized_volume_sc']):,.0f} sc."
        )

    bullets = []
    recommended_actions = []
    if action == "vender":
        bullets.append("Prioridade comercial: avaliar novas vendas/hedges para aproximar a posição da política.")
        recommended_actions.append("Avaliar novas fixações, vendas a termo ou derivativos até atingir pelo menos o piso da política.")
    elif action == "segurar":
        bullets.append("Prioridade comercial: evitar ampliar a exposição vendida antes de revisar a política e o risco de produção.")
        recommended_actions.append("Revisar a posição já vendida/protegida antes de ampliar novas travas.")
    else:
        bullets.append("Prioridade comercial: manter disciplina de preço e acompanhar evolução de produção, mercado e política.")
        recommended_actions.append("Seguir monitorando preços, política e evolução da produção antes de novas decisões relevantes.")

    if budget_cost_total > 0:
        bullets.append(
            f"Há {round(budget_cost_total):,.0f} em custo orçamento cadastrado, o que ajuda a calibrar meta de margem e preço mínimo de venda."
        )
    if news_count:
        bullets.append(f"Foram identificados {news_count} posts recentes de mercado que podem contextualizar a decisão comercial.")

    culture_actions = []
    for item in payload["tables"]["top_cultures"][:3]:
        if item["coverage_ratio"] < 0.5 and item["uncovered_volume_sc"] > 0:
            culture_actions.append(
                f"{item['label']}: cobertura de {_format_pct(item['coverage_ratio'])}% e saldo aberto de {round(item['uncovered_volume_sc']):,.0f} sc."
            )
        elif item["coverage_ratio"] > 1.0:
            culture_actions.append(
                f"{item['label']}: cobertura de {_format_pct(item['coverage_ratio'])}% com atenção para excesso de venda/proteção."
            )

    warnings = []
    if payload["metrics"]["forms_pending_count"] > 0:
        warnings.append(
            f"Existem {payload['metrics']['forms_pending_count']} formulários-chave ainda pendentes, o que pode reduzir a confiança dos insights."
        )
    if status == "sem_politica":
        warnings.append("Sem política ativa, a recomendação fica tática e perde referência formal de disciplina comercial.")
    if metrics["net_production_sc"] <= 0:
        warnings.append("Produção líquida zerada ou negativa após considerar pagamentos físicos; revise base produtiva e compromissos.")

    return {
        "status": status,
        "recommended_action": action,
        "executive_summary": " ".join(executive_summary),
        "bullets": bullets,
        "recommended_actions": recommended_actions,
        "culture_actions": culture_actions,
        "warnings": warnings,
    }


def _build_written_cards(payload, local_insights):
    metrics = payload["metrics"]
    mtm = payload["derivatives_open_mtm"]
    dashboard = payload["dashboard_stories"]
    cards = []

    cards.append(
        {
            "key": "executive",
            "title": "Devolutiva executiva",
            "body": local_insights.get("executive_summary") or "Sem devolutiva disponível.",
            "bullets": [],
        }
    )

    cards.append(
        {
            "key": "attention",
            "title": "Pontos de atenção",
            "body": None,
            "bullets": local_insights.get("bullets") or [],
        }
    )

    open_negative_count = mtm.get("open_negative_count", 0)
    open_negative_total = mtm.get("open_negative_total_brl", 0)
    worst_exchange = mtm.get("worst_exchange")
    mtm_bullets = []
    if worst_exchange:
        mtm_bullets.append(
            f"A bolsa com maior pressão de MTM negativo em aberto é {worst_exchange['label']}, com cerca de R$ {worst_exchange['negative_brl']:,.0f} negativos."
        )
    for item in mtm.get("exchanges", [])[:3]:
        mtm_bullets.append(
            f"{item['label']}: {item['open_count']} operações em aberto e MTM líquido aproximado de R$ {item['net_brl']:,.0f}."
        )
    mtm_body = (
        f"Foram identificadas {open_negative_count} operações derivativas em aberto com MTM/ajustes negativos, somando aproximadamente R$ {open_negative_total:,.0f}."
        if open_negative_count
        else "Não foram identificadas operações derivativas em aberto com MTM negativo relevante neste momento."
    )
    cards.append(
        {
            "key": "mtm_open_risk",
            "title": "Risco de MTM negativo nos derivativos em aberto",
            "body": mtm_body,
            "bullets": mtm_bullets,
        }
    )

    cards.append(
        {
            "key": "recommended_actions",
            "title": "Ações recomendadas",
            "body": None,
            "bullets": local_insights.get("recommended_actions") or local_insights.get("culture_actions") or [],
        }
    )

    maturity = payload.get("maturity_story") or {}
    cards.append(
        {
            "key": "maturities",
            "title": "Leitura de vencimentos",
            "body": maturity.get("body") or "Sem concentração relevante de vencimentos no curto prazo.",
            "bullets": maturity.get("bullets") or [],
        }
    )

    cards.append(
        {
            "key": "warnings",
            "title": "Riscos e avisos",
            "body": None,
            "bullets": local_insights.get("warnings") or [],
        }
    )

    if metrics.get("commercialization_coverage_ratio", 0) > 1:
        cards.append(
            {
                "key": "overhedge_context",
                "title": "Leitura da cobertura acima da política",
                "body": (
                    f"A posição comercial/protegida está em {round(metrics['commercialization_coverage_ratio'] * 100, 1)}% da produção líquida, acima do teto da política. "
                    "Neste cenário, o foco deixa de ser vender mais e passa a ser administrar execução, risco produtivo e eventual necessidade de recomposição."
                ),
                "bullets": [],
            }
        )

    cards.extend(
        [
            {
                "key": "hedge_floor_gap",
                "title": "Leitura do piso da política",
                "body": dashboard["hedge_floor_gap"],
                "bullets": [],
            },
            {
                "key": "hedge_band_context",
                "title": "Leitura da faixa de hedge sobre produção líquida",
                "body": dashboard["hedge_band_context"],
                "bullets": [],
            },
            {
                "key": "commercial_mix",
                "title": "Mix de comercialização",
                "body": dashboard["commercial_mix"],
                "bullets": [],
            },
            {
                "key": "budget_context",
                "title": "Leitura de custo orçamento",
                "body": dashboard["budget_context"],
                "bullets": [],
            },
            {
                "key": "cashflow_30d",
                "title": "Fluxo dos próximos 30 dias",
                "body": dashboard["cashflow_30d"],
                "bullets": [],
            },
            {
                "key": "cashflow_7d",
                "title": "Pressão imediata de caixa",
                "body": dashboard["cashflow_7d"],
                "bullets": [],
            },
            {
                "key": "derivatives_open_status",
                "title": "Situação dos derivativos em aberto",
                "body": dashboard["derivatives_open_status"],
                "bullets": [],
            },
            {
                "key": "derivatives_settlement",
                "title": "Derivativos com liquidação próxima",
                "body": dashboard["derivatives_settlement"],
                "bullets": [],
            },
            {
                "key": "group_concentration",
                "title": "Concentração por grupo",
                "body": dashboard["group_concentration"],
                "bullets": [],
            },
            {
                "key": "subgroup_concentration",
                "title": "Concentração por subgrupo",
                "body": dashboard["subgroup_concentration"],
                "bullets": [],
            },
            {
                "key": "culture_focus",
                "title": "Ativo que mais exige foco",
                "body": dashboard["culture_focus"],
                "bullets": [],
            },
            {
                "key": "open_volume_story",
                "title": "Saldo ainda aberto",
                "body": dashboard["open_volume_story"],
                "bullets": [],
            },
            {
                "key": "policy_recency",
                "title": "Atualidade da política",
                "body": dashboard["policy_recency"],
                "bullets": [],
            },
            {
                "key": "news_context",
                "title": "Contexto de mercado",
                "body": dashboard["news_context"],
                "bullets": [],
            },
            {
                "key": "forms_quality",
                "title": "Qualidade da base para decisão",
                "body": dashboard["forms_quality"],
                "bullets": [],
            },
            {
                "key": "physical_payments_context",
                "title": "Impacto dos pagamentos físicos",
                "body": dashboard["physical_payments_context"],
                "bullets": [],
            },
            {
                "key": "sales_vs_production",
                "title": "Venda física versus produção",
                "body": dashboard["sales_vs_production"],
                "bullets": [],
            },
            {
                "key": "derivatives_vs_production",
                "title": "Derivativos versus produção",
                "body": dashboard["derivatives_vs_production"],
                "bullets": [],
            },
            {
                "key": "operational_intensity",
                "title": "Intensidade operacional",
                "body": dashboard["operational_intensity"],
                "bullets": [],
            },
            {
                "key": "mtm_exchange_concentration",
                "title": "Concentração de risco por bolsa",
                "body": dashboard["mtm_exchange_concentration"],
                "bullets": [],
            },
        ]
    )

    return cards


def _build_question_lab(payload, local_insights):
    metrics = payload["metrics"]
    operations = payload["operations"]
    data_quality = payload["data_quality"]
    top_cultures = payload["tables"]["top_cultures"]
    upcoming_maturities = payload["tables"]["upcoming_maturities"]

    coverage_ratio = metrics.get("commercialization_coverage_ratio", 0)
    uncovered_volume = metrics.get("uncovered_volume_sc", 0)
    floor_gap = metrics.get("volume_to_policy_floor_sc", 0)
    net_production = metrics.get("net_production_sc", 0)
    commercialized_volume = metrics.get("commercialized_volume_sc", 0)
    policy_min_ratio = metrics.get("policy_min_ratio")

    open_sales_bullets = [
        f"Produção líquida considerada: {_format_sc(net_production)}.",
        f"Volume já comercializado/protegido: {_format_sc(commercialized_volume)}.",
        f"Cobertura atual: {_format_pct(coverage_ratio)}% da produção líquida.",
    ]
    if floor_gap > 0:
        open_sales_bullets.append(f"Faltam {_format_sc(floor_gap)} para atingir o piso da política ativa.")
    if top_cultures:
        open_sales_bullets.append(
            f"Ativo que mais pesa no saldo aberto: {top_cultures[0]['label']} com {_format_sc(top_cultures[0]['uncovered_volume_sc'])} ainda sem cobertura."
        )
    open_sales_summary = (
        f"Ainda faltam aproximadamente {_format_sc(uncovered_volume)} para fixar ou proteger frente à produção líquida do filtro atual."
        if uncovered_volume > 0
        else "No filtro atual, não há saldo aberto relevante entre produção líquida e posição já comercializada/protegida."
    )
    if policy_min_ratio is None:
        open_sales_summary += " Não há política ativa suficiente no recorte para comparar esse saldo com um piso formal."
    elif floor_gap <= 0:
        open_sales_summary += " O piso da política já está atendido neste recorte."

    near_titles = []
    for item in upcoming_maturities[:4]:
        near_titles.append(f"{item['type']}: {item['title']} em {item['date']}.")
    expiring_bills_summary = (
        f"Há {operations['upcoming_7d_count']} eventos nos próximos 7 dias e {operations['upcoming_30d_count']} nos próximos 30 dias com potencial de pressionar caixa ou execução."
        if operations["upcoming_30d_count"] > 0
        else "Não há vencimentos relevantes nos próximos 30 dias dentro do filtro atual."
    )
    expiring_bills_bullets = [
        f"Vendas físicas próximas: {operations['physical_sales_30d_count']}.",
        f"Pagamentos físicos próximos: {operations['physical_payments_30d_count']}.",
        f"Pagamentos de caixa próximos: {operations['cash_payments_30d_count']}.",
        f"Derivativos com liquidação próxima: {operations['derivatives_30d_count']}.",
    ] + near_titles

    missing_sources = [item for item in data_quality["sources"] if item["status"] == "missing"]
    available_sources = [item for item in data_quality["sources"] if item["status"] == "ok"]
    forms_gap_summary = (
        f"Existem {len(missing_sources)} base(s) sem registros no filtro atual, o que reduz a confiança da leitura consolidada."
        if missing_sources
        else "As principais bases do Insights têm registros no filtro atual, então a leitura está mais completa."
    )
    forms_gap_bullets = [
        f"Sem base em: {', '.join(item['label'] for item in missing_sources)}."
        if missing_sources
        else "Nenhuma frente crítica apareceu zerada neste filtro."
    ]
    if available_sources:
        available_labels = ", ".join([f"{item['label']} ({item['count']})" for item in available_sources[:4]])
        forms_gap_bullets.append(
            f"Com base disponível em: {available_labels}."
        )

    priority_bullets = []
    for item in local_insights.get("bullets", [])[:2]:
        priority_bullets.append(item)
    for item in local_insights.get("recommended_actions", [])[:2]:
        priority_bullets.append(item)
    for item in local_insights.get("warnings", [])[:2]:
        priority_bullets.append(item)
    if not priority_bullets:
        priority_bullets.append("Sem alertas adicionais relevantes no filtro atual.")

    return [
        {
            "id": "open-sales",
            "title": "Quanto ainda falta fixar nas vendas?",
            "summary": open_sales_summary,
            "bullets": open_sales_bullets,
            "stats": [
                {"label": "Saldo aberto", "value": _format_sc(uncovered_volume)},
                {"label": "Cobertura atual", "value": f"{_format_pct(coverage_ratio)}%"},
                {"label": "Piso da política", "value": f"{_format_pct(policy_min_ratio)}%" if policy_min_ratio is not None else "Sem política"},
            ],
        },
        {
            "id": "expiring-bills",
            "title": "Quais compromissos vencem em breve?",
            "summary": expiring_bills_summary,
            "bullets": expiring_bills_bullets,
            "stats": [
                {"label": "Próx. 7 dias", "value": str(operations["upcoming_7d_count"])},
                {"label": "Próx. 30 dias", "value": str(operations["upcoming_30d_count"])},
                {"label": "Derivativos", "value": str(operations["derivatives_30d_count"])},
            ],
        },
        {
            "id": "forms-gap",
            "title": "Quais dados ainda faltam para melhorar a análise?",
            "summary": forms_gap_summary,
            "bullets": forms_gap_bullets,
            "stats": [
                {"label": "Bases faltantes", "value": str(len(missing_sources))},
                {"label": "Bases com dados", "value": str(len(available_sources))},
                {"label": "Frentes avaliadas", "value": str(len(data_quality["sources"]))},
            ],
        },
        {
            "id": "priority-actions",
            "title": "O que merece atenção agora?",
            "summary": local_insights.get("executive_summary") or "Sem leitura executiva disponível no momento.",
            "bullets": priority_bullets,
            "stats": [
                {"label": "Ação sugerida", "value": str(local_insights.get("recommended_action") or "monitorar").capitalize()},
                {"label": "MTM negativo", "value": _format_brl(payload["derivatives_open_mtm"].get("open_negative_total_brl", 0))},
                {"label": "Alertas", "value": str(len(local_insights.get("warnings", [])) + len(local_insights.get("bullets", [])))},
            ],
        },
    ]


def _build_dashboard_stories(payload):
    metrics = payload["metrics"]
    mtm = payload["derivatives_open_mtm"]
    context = payload["context"]
    concentration = payload["concentration"]
    operations = payload["operations"]

    coverage_ratio = metrics.get("commercialization_coverage_ratio", 0)
    policy_min = metrics.get("policy_min_ratio")
    policy_max = metrics.get("policy_max_ratio")
    physical_ratio = (metrics.get("physical_sold_volume_sc", 0) / metrics["net_production_sc"]) if metrics.get("net_production_sc", 0) > 0 else 0
    derivative_ratio = (metrics.get("derivative_commodity_volume_sc", 0) / metrics["net_production_sc"]) if metrics.get("net_production_sc", 0) > 0 else 0

    if policy_min is None:
        hedge_floor_gap = "Não há piso de política ativo no recorte filtrado, então a leitura comercial precisa ser feita com mais prudência e sem âncora formal."
    elif metrics.get("volume_to_policy_floor_sc", 0) > 0:
        hedge_floor_gap = (
            f"Faltam aproximadamente {_format_sc(metrics['volume_to_policy_floor_sc'])} para alcançar o piso da política ativa. "
            "Enquanto esse volume não for protegido ou vendido, o produtor segue mais exposto do que o desejado."
        )
    else:
        hedge_floor_gap = "O piso da política já está atendido no recorte atual, o que reduz a urgência por novas vendas defensivas."

    if policy_min is None or policy_max is None:
        hedge_band_context = "Sem faixa mínima e máxima válida no filtro atual, a comparação de hedge fica apenas indicativa."
    elif coverage_ratio < policy_min:
        hedge_band_context = (
            f"A cobertura atual está em {_format_pct(coverage_ratio)}%, abaixo do mínimo de {_format_pct(policy_min)}%. "
            "O dashboard sugere espaço para avançar em proteção se a estratégia comercial permitir."
        )
    elif coverage_ratio > policy_max:
        hedge_band_context = (
            f"A cobertura atual está em {_format_pct(coverage_ratio)}%, acima do teto de {_format_pct(policy_max)}%. "
            "O foco agora tende a ser disciplina de execução e controle de risco produtivo."
        )
    else:
        hedge_band_context = (
            f"A cobertura atual está em {_format_pct(coverage_ratio)}%, dentro da faixa de {_format_pct(policy_min)}% a {_format_pct(policy_max)}%. "
            "Isso mostra aderência da posição à política de hedge."
        )

    commercial_mix = (
        f"Da cobertura total sobre a produção líquida, aproximadamente {_format_pct(physical_ratio)}% vem de vendas físicas e {_format_pct(derivative_ratio)}% vem de derivativos. "
        "Esse mix ajuda a entender se a proteção está mais concentrada em preço físico ou em instrumentos de bolsa."
    )

    budget_cost_total = metrics.get("budget_cost_total_brl", 0)
    total_area = metrics.get("total_area_ha", 0)
    if budget_cost_total > 0 and total_area > 0:
        budget_context = (
            f"O sistema soma {_format_brl(budget_cost_total)} em custo orçamento, o equivalente a cerca de {_format_brl(budget_cost_total / total_area)} por hectare no recorte filtrado. "
            "Esse número ajuda a calibrar disciplina de margem e preço mínimo."
        )
    elif budget_cost_total > 0:
        budget_context = (
            f"O sistema soma {_format_brl(budget_cost_total)} em custo orçamento no recorte atual. "
            "Mesmo sem área suficiente para rateio, essa base já ajuda a contextualizar metas de margem."
        )
    else:
        budget_context = "Não há custo orçamento suficiente no filtro atual, então a leitura de margem fica menos precisa."

    cashflow_30d = (
        f"Há {operations['upcoming_30d_count']} eventos financeiros ou de liquidação nos próximos 30 dias, sendo "
        f"{operations['physical_sales_30d_count']} vendas físicas, {operations['physical_payments_30d_count']} pagamentos físicos, "
        f"{operations['cash_payments_30d_count']} pagamentos de caixa e {operations['derivatives_30d_count']} derivativos."
    )

    cashflow_7d = (
        f"Nos próximos 7 dias, o sistema mostra {operations['upcoming_7d_count']} eventos com potencial de pressionar caixa ou execução comercial. "
        "Esse é o horizonte mais sensível para monitoramento diário."
    )

    derivatives_open_status = (
        f"Existem {operations['derivatives_open_count']} derivativos em aberto e {operations['derivatives_closed_count']} já encerrados no recorte. "
        "Para decisão comercial, o mais relevante é acompanhar os que seguem em aberto porque ainda carregam risco."
    )

    if operations["derivatives_30d_count"] > 0:
        derivatives_settlement = (
            f"Foram identificados {operations['derivatives_30d_count']} derivativos com liquidação nos próximos 30 dias. "
            "Isso pede atenção para ajuste, caixa e eventual rolagem."
        )
    else:
        derivatives_settlement = "Não há derivativos com liquidação relevante nos próximos 30 dias dentro do recorte atual."

    top_group = concentration.get("top_group")
    if top_group:
        group_concentration = (
            f"O grupo {top_group['label']} concentra aproximadamente {_format_pct(top_group['share'])}% da produção líquida monitorada neste filtro. "
            "Esse peso tende a influenciar de forma desproporcional a leitura consolidada."
        )
    else:
        group_concentration = "Não foi possível identificar concentração relevante por grupo no recorte atual."

    top_subgroup = concentration.get("top_subgroup")
    if top_subgroup:
        subgroup_concentration = (
            f"O subgrupo {top_subgroup['label']} concentra aproximadamente {_format_pct(top_subgroup['share'])}% da produção líquida monitorada neste filtro. "
            "Vale acompanhar esse recorte com atenção por ser o principal formador da leitura."
        )
    else:
        subgroup_concentration = "Não foi possível identificar concentração relevante por subgrupo no recorte atual."

    top_culture = payload["tables"]["top_cultures"][0] if payload["tables"]["top_cultures"] else None
    if top_culture:
        culture_focus = (
            f"O ativo com maior peso no dashboard é {top_culture['label']}, com produção líquida de {_format_sc(top_culture['net_production_sc'])} "
            f"e cobertura de {_format_pct(top_culture['coverage_ratio'])}%."
        )
    else:
        culture_focus = "Nenhum ativo com produção relevante foi identificado no filtro atual."

    if metrics.get("over_hedged_volume_sc", 0) > 0:
        open_volume_story = (
            f"A posição está acima do teto em cerca de {_format_sc(metrics['over_hedged_volume_sc'])}. "
            "Nesse cenário, vender mais pode ampliar o descasamento entre cobertura e produção."
        )
    elif metrics.get("uncovered_volume_sc", 0) > 0:
        open_volume_story = (
            f"Ainda restam aproximadamente {_format_sc(metrics['uncovered_volume_sc'])} sem cobertura frente à produção líquida. "
            "Esse saldo representa a principal exposição comercial em aberto."
        )
    else:
        open_volume_story = "Não há saldo aberto relevante entre produção líquida e posição comercial no recorte filtrado."

    if context.get("policy_reference_month"):
        policy_recency = (
            f"A política utilizada nesta leitura tem referência em {context['policy_reference_month']}. "
            "Manter essa data atualizada é importante para que o insight continue aderente ao momento comercial."
        )
    else:
        policy_recency = "O filtro atual não trouxe mês de política de hedge ativo para servir como referência formal."

    if context.get("recent_news_count", 0) > 0:
        news_context = (
            f"Foram encontrados {context['recent_news_count']} posts recentes de mercado vinculados ao sistema. "
            "Esse material pode complementar a decisão tática de venda, trava ou espera."
        )
    else:
        news_context = "Não há posts recentes de mercado suficientes para complementar a leitura no filtro atual."

    if metrics.get("forms_pending_count", 0) > 0:
        forms_quality = (
            f"Existem {metrics['forms_pending_count']} frentes sem base suficiente no filtro atual. "
            "Quanto mais completa estiver a alimentação dos dashboards, mais confiável fica a devolutiva do Insights."
        )
    else:
        forms_quality = "Os principais dashboards têm base cadastrada no filtro atual, o que melhora a confiabilidade das devolutivas."

    if metrics.get("physical_payment_volume_sc", 0) > 0:
        physical_payments_context = (
            f"Os pagamentos físicos já comprometem {_format_sc(metrics['physical_payment_volume_sc'])} da produção, reduzindo a base líquida disponível para venda ou hedge. "
            "Esse ajuste é importante para evitar leitura inflada de oferta."
        )
    else:
        physical_payments_context = "Não há pagamentos físicos relevantes reduzindo a produção líquida no recorte atual."

    sales_vs_production = (
        f"As vendas físicas representam aproximadamente {_format_pct(physical_ratio)}% da produção líquida considerada. "
        "Essa é a parcela já travada diretamente no canal físico."
    )

    derivatives_vs_production = (
        f"Os derivativos de commodity representam aproximadamente {_format_pct(derivative_ratio)}% da produção líquida considerada. "
        "Esse percentual mostra quanto da proteção está passando por bolsa ou instrumento financeiro."
    )

    operational_intensity = (
        f"O recorte atual reúne {operations['crop_boards_count']} registros de produção, {operations['physical_sales_count']} vendas físicas, "
        f"{operations['derivatives_count']} derivativos, {operations['physical_payments_count']} pagamentos físicos e {operations['cash_payments_count']} pagamentos de caixa. "
        "Quanto maior essa intensidade operacional, maior a necessidade de disciplina na leitura consolidada."
    )

    if mtm.get("worst_exchange"):
        mtm_exchange_concentration = (
            f"A maior concentração de MTM negativo em aberto está na bolsa {mtm['worst_exchange']['label']}, com aproximadamente {_format_brl(mtm['worst_exchange']['negative_brl'])} em pressão negativa. "
            "Esse é o principal ponto de monitoramento de ajuste entre as bolsas hoje."
        )
    elif mtm.get("open_count", 0) > 0:
        mtm_exchange_concentration = (
            f"Há {mtm['open_count']} derivativos em aberto distribuídos entre as bolsas monitoradas, mas sem concentração negativa relevante de MTM neste momento."
        )
    else:
        mtm_exchange_concentration = "Não há derivativos em aberto suficientes para caracterizar concentração de risco por bolsa."

    return {
        "hedge_floor_gap": hedge_floor_gap,
        "hedge_band_context": hedge_band_context,
        "commercial_mix": commercial_mix,
        "budget_context": budget_context,
        "cashflow_30d": cashflow_30d,
        "cashflow_7d": cashflow_7d,
        "derivatives_open_status": derivatives_open_status,
        "derivatives_settlement": derivatives_settlement,
        "group_concentration": group_concentration,
        "subgroup_concentration": subgroup_concentration,
        "culture_focus": culture_focus,
        "open_volume_story": open_volume_story,
        "policy_recency": policy_recency,
        "news_context": news_context,
        "forms_quality": forms_quality,
        "physical_payments_context": physical_payments_context,
        "sales_vs_production": sales_vs_production,
        "derivatives_vs_production": derivatives_vs_production,
        "operational_intensity": operational_intensity,
        "mtm_exchange_concentration": mtm_exchange_concentration,
    }


def _call_openai_insights(payload, local_insights):
    api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
    if not api_key:
        return None

    try:
        from openai import OpenAI
    except Exception:
        return None

    model = getattr(settings, "OPENAI_INSIGHTS_MODEL", "gpt-5-mini")
    client = OpenAI(api_key=api_key)

    prompt_payload = {
        "metrics": payload["metrics"],
        "top_cultures": payload["tables"]["top_cultures"][:5],
        "maturities": payload["tables"]["upcoming_maturities"][:5],
        "recent_news_titles": payload["context"]["recent_news_titles"][:5],
        "local_insights": local_insights,
    }

    instructions = (
        "Você é um analista sênior de comercialização agrícola e hedge para produtor rural brasileiro. "
        "Leia os números do sistema e devolva uma análise objetiva, prudente e acionável. "
        "Não invente dados. Se faltar informação, diga isso claramente. "
        "Responda SOMENTE em JSON válido com as chaves: executive_summary, bullets, recommended_actions, warnings."
    )

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": instructions},
            {
                "role": "user",
                "content": f"Analise estes dados de comercialização e hedge:\n{json.dumps(prompt_payload, ensure_ascii=False)}",
            },
        ],
    )
    output_text = (getattr(response, "output_text", None) or "").strip()
    if not output_text:
        return None
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError:
        return {
            "model": model,
            "parsed": {
                "executive_summary": output_text,
                "bullets": [],
                "recommended_actions": [],
                "warnings": ["A IA respondeu fora do formato estruturado esperado."],
            },
        }
    return {"model": model, "parsed": parsed}


def build_insights_payload(request):
    user = request.user
    selected_localities = _parse_multi_value_param(request, "localidade")

    crop_boards = _filter_locality_rows(
        list(
            _apply_filters(
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
        ),
        selected_localities,
        lambda row: row.localidade or [],
    )
    physical_sales = _filter_locality_rows(
        list(
            _apply_filters(
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
        ),
        selected_localities,
        lambda row: [row.localidade],
    )
    physical_payments = list(
        _apply_filters(
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
        _apply_filters(
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
        _apply_filters(
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
    hedge_policies = list(
        _apply_filters(
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
        )
    )
    budget_costs = list(
        _apply_filters(
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
        )
    )

    market_news_qs = _scope_queryset(
        MarketNewsPost.objects.select_related("tenant", "created_by", "published_by"),
        user,
    )
    if not (user.is_superuser or user.is_tenant_admin()):
        market_news_qs = market_news_qs.filter(status_artigo=MarketNewsPost.STATUS_PUBLISHED)
    recent_news = list(market_news_qs.order_by("-data_publicacao", "-created_at")[:8])

    production_total = sum(abs(_to_number(item.producao_total)) for item in crop_boards)
    total_area = sum(abs(_to_number(item.area)) for item in crop_boards)
    physical_payment_volume = sum(abs(_to_number(item.volume)) for item in physical_payments)
    net_production = max(production_total - physical_payment_volume, 0)
    physical_sold_volume = sum(abs(_to_number(item.volume_fisico)) for item in physical_sales)
    derivative_commodity_volume = sum(
        _get_derivative_standard_volume(item)
        for item in derivatives
        if _normalize_text(item.moeda_ou_cmdtye) == "cmdtye"
    )
    commercialized_volume = physical_sold_volume + derivative_commodity_volume
    commercialization_ratio = (commercialized_volume / net_production) if net_production > 0 else 0

    current_month = timezone.localdate().replace(day=1)
    active_policy_row = _select_active_policy_for_reference_date(hedge_policies, current_month)
    current_policy = active_policy_row["instance"] if active_policy_row else None

    policy_min_ratio = active_policy_row["min_ratio"] if active_policy_row else None
    policy_max_ratio = active_policy_row["max_ratio"] if active_policy_row else None
    min_target_volume = (policy_min_ratio or 0) * net_production if policy_min_ratio is not None else None
    max_target_volume = (policy_max_ratio or 0) * net_production if policy_max_ratio is not None else None
    uncovered_volume = max(net_production - commercialized_volume, 0)
    volume_to_policy_floor = max((min_target_volume or 0) - commercialized_volume, 0) if min_target_volume is not None else 0
    over_hedged_volume = max(commercialized_volume - (max_target_volume or commercialized_volume), 0) if max_target_volume is not None else 0

    top_culture_map = defaultdict(lambda: {"production": 0.0, "physical": 0.0, "derivatives": 0.0, "physical_payments": 0.0})
    for row in crop_boards:
        label = _read_label(row.cultura, "Sem ativo")
        top_culture_map[label]["production"] += abs(_to_number(row.producao_total))
    for row in physical_sales:
        label = _read_label(row.cultura or row.cultura_produto, "Sem ativo")
        top_culture_map[label]["physical"] += abs(_to_number(row.volume_fisico))
    for row in physical_payments:
        label = _read_label(row.fazer_frente_com, "Sem ativo")
        top_culture_map[label]["physical_payments"] += abs(_to_number(row.volume))
    for row in derivatives:
        label = _read_label(row.ativo or row.destino_cultura, "Sem ativo")
        top_culture_map[label]["derivatives"] += _get_derivative_standard_volume(row)

    top_cultures = []
    for label, values in top_culture_map.items():
        production = max(values["production"] - values["physical_payments"], 0)
        covered = values["physical"] + values["derivatives"]
        top_cultures.append(
            {
                "label": label,
                "net_production_sc": round(production, 2),
                "physical_sc": round(values["physical"], 2),
                "derivatives_sc": round(values["derivatives"], 2),
                "coverage_ratio": round((covered / production), 4) if production > 0 else 0,
                "uncovered_volume_sc": round(max(production - covered, 0), 2),
            }
        )
    top_cultures.sort(key=lambda item: max(item["net_production_sc"], item["physical_sc"] + item["derivatives_sc"]), reverse=True)

    group_map = defaultdict(lambda: {"production": 0.0})
    subgroup_map = defaultdict(lambda: {"production": 0.0})
    for row in crop_boards:
        group_map[_read_label(getattr(row, "grupo", None), "Sem grupo")]["production"] += abs(_to_number(row.producao_total))
        subgroup_map[_read_label(getattr(row, "subgrupo", None), "Sem subgrupo")]["production"] += abs(_to_number(row.producao_total))

    total_group_production = sum(item["production"] for item in group_map.values())
    total_subgroup_production = sum(item["production"] for item in subgroup_map.values())
    top_group = None
    top_subgroup = None
    if total_group_production > 0 and group_map:
        group_label, group_values = max(group_map.items(), key=lambda entry: entry[1]["production"])
        top_group = {
            "label": group_label,
            "production_sc": round(group_values["production"], 2),
            "share": round(group_values["production"] / total_group_production, 4),
        }
    if total_subgroup_production > 0 and subgroup_map:
        subgroup_label, subgroup_values = max(subgroup_map.items(), key=lambda entry: entry[1]["production"])
        top_subgroup = {
            "label": subgroup_label,
            "production_sc": round(subgroup_values["production"], 2),
            "share": round(subgroup_values["production"] / total_subgroup_production, 4),
        }

    upcoming_maturities = []
    today = timezone.localdate()
    for row in physical_sales:
        if row.data_pagamento and row.data_pagamento >= today:
            upcoming_maturities.append({"type": "Venda Fisico", "title": row.cultura_produto or _read_label(row.cultura), "date": row.data_pagamento.isoformat()})
    for row in physical_payments:
        if row.data_pagamento and row.data_pagamento >= today:
            upcoming_maturities.append({"type": "Pgto Fisico", "title": row.descricao or _read_label(row.fazer_frente_com), "date": row.data_pagamento.isoformat()})
    for row in cash_payments:
        if row.data_pagamento and row.data_pagamento >= today:
            upcoming_maturities.append({"type": "Pgto Caixa", "title": row.descricao or _read_label(row.fazer_frente_com), "date": row.data_pagamento.isoformat()})
    for row in derivatives:
        if row.data_liquidacao and row.data_liquidacao >= today:
            upcoming_maturities.append({"type": "Derivativo", "title": row.nome_da_operacao or row.cod_operacao_mae or "Operacao derivativa", "date": row.data_liquidacao.isoformat()})
    upcoming_maturities.sort(key=lambda item: item["date"])

    open_derivatives = [
        item
        for item in derivatives
        if "encerr" not in _normalize_text(getattr(item, "status_operacao", ""))
    ]
    exchange_mtm_map = defaultdict(lambda: {"open_count": 0, "negative_count": 0, "negative_brl": 0.0, "net_brl": 0.0})
    for item in open_derivatives:
        exchange_label = (
            getattr(item, "bolsa_ref", None)
            or getattr(item, "ctrbolsa", None)
            or getattr(item, "instituicao", None)
            or "Sem bolsa"
        )
        mtm_value = _to_number(getattr(item, "ajustes_totais_brl", 0))
        node = exchange_mtm_map[exchange_label]
        node["open_count"] += 1
        node["net_brl"] += mtm_value
        if mtm_value < 0:
            node["negative_count"] += 1
            node["negative_brl"] += abs(mtm_value)

    exchange_mtm_rows = [
        {
            "label": label,
            "open_count": values["open_count"],
            "negative_count": values["negative_count"],
            "negative_brl": round(values["negative_brl"], 2),
            "net_brl": round(values["net_brl"], 2),
        }
        for label, values in exchange_mtm_map.items()
    ]
    exchange_mtm_rows.sort(key=lambda item: (item["negative_brl"], item["open_count"]), reverse=True)
    worst_exchange = exchange_mtm_rows[0] if exchange_mtm_rows and exchange_mtm_rows[0]["negative_brl"] > 0 else None

    next_30_days = today + timedelta(days=30)
    next_7_days = today + timedelta(days=7)
    near_maturities = [item for item in upcoming_maturities if item["date"] <= next_30_days.isoformat()]
    near_maturities_7d = [item for item in upcoming_maturities if item["date"] <= next_7_days.isoformat()]
    maturity_type_map = defaultdict(int)
    for item in near_maturities:
        maturity_type_map[item["type"]] += 1
    maturity_bullets = [
        f"{label}: {count} vencimento(s) nos próximos 30 dias."
        for label, count in sorted(maturity_type_map.items(), key=lambda entry: entry[1], reverse=True)
    ]
    maturity_body = (
        f"Foram identificados {len(near_maturities)} vencimentos nos próximos 30 dias. Esse bloco merece atenção porque pode antecipar necessidade de caixa, rolagem ou decisão comercial."
        if near_maturities
        else "Não há concentração relevante de vencimentos nos próximos 30 dias."
    )

    forms_pending_count = sum(
        1 for count in [len(crop_boards), len(physical_sales), len(derivatives), len(hedge_policies), len(budget_costs), len(physical_payments), len(cash_payments)] if count == 0
    )
    source_rows = [
        {"key": "crop_boards", "label": "Quadro Safra", "count": len(crop_boards)},
        {"key": "physical_sales", "label": "Vendas Físicas", "count": len(physical_sales)},
        {"key": "derivatives", "label": "Derivativos", "count": len(derivatives)},
        {"key": "hedge_policies", "label": "Política de Hedge", "count": len(hedge_policies)},
        {"key": "budget_costs", "label": "Custo Orçamento", "count": len(budget_costs)},
        {"key": "physical_payments", "label": "Pagamentos Físicos", "count": len(physical_payments)},
        {"key": "cash_payments", "label": "Pagamentos de Caixa", "count": len(cash_payments)},
    ]

    metrics = {
        "production_total_sc": round(production_total, 2),
        "physical_payment_volume_sc": round(physical_payment_volume, 2),
        "net_production_sc": round(net_production, 2),
        "commercialized_volume_sc": round(commercialized_volume, 2),
        "physical_sold_volume_sc": round(physical_sold_volume, 2),
        "derivative_commodity_volume_sc": round(derivative_commodity_volume, 2),
        "commercialization_coverage_ratio": round(commercialization_ratio, 4),
        "policy_min_ratio": round(policy_min_ratio, 4) if policy_min_ratio is not None else None,
        "policy_max_ratio": round(policy_max_ratio, 4) if policy_max_ratio is not None else None,
        "volume_to_policy_floor_sc": round(volume_to_policy_floor, 2),
        "uncovered_volume_sc": round(uncovered_volume, 2),
        "over_hedged_volume_sc": round(over_hedged_volume, 2),
        "budget_cost_total_brl": round(sum(_to_number(item.valor) for item in budget_costs), 2),
        "total_area_ha": round(total_area, 2),
        "forms_pending_count": forms_pending_count,
    }
    payload = {
        "generated_at": timezone.now().isoformat(),
        "metrics": metrics,
        "tables": {
            "top_cultures": top_cultures[:8],
            "upcoming_maturities": upcoming_maturities[:8],
        },
        "concentration": {
            "top_group": top_group,
            "top_subgroup": top_subgroup,
        },
        "operations": {
            "crop_boards_count": len(crop_boards),
            "physical_sales_count": len(physical_sales),
            "derivatives_count": len(derivatives),
            "physical_payments_count": len(physical_payments),
            "cash_payments_count": len(cash_payments),
            "upcoming_30d_count": len(near_maturities),
            "upcoming_7d_count": len(near_maturities_7d),
            "physical_sales_30d_count": sum(1 for item in near_maturities if item["type"] == "Venda Fisico"),
            "physical_payments_30d_count": sum(1 for item in near_maturities if item["type"] == "Pgto Fisico"),
            "cash_payments_30d_count": sum(1 for item in near_maturities if item["type"] == "Pgto Caixa"),
            "derivatives_30d_count": sum(1 for item in near_maturities if item["type"] == "Derivativo"),
            "derivatives_open_count": len(open_derivatives),
            "derivatives_closed_count": max(len(derivatives) - len(open_derivatives), 0),
        },
        "derivatives_open_mtm": {
            "open_count": len(open_derivatives),
            "open_negative_count": sum(1 for item in open_derivatives if _to_number(getattr(item, "ajustes_totais_brl", 0)) < 0),
            "open_negative_total_brl": round(sum(abs(_to_number(getattr(item, "ajustes_totais_brl", 0))) for item in open_derivatives if _to_number(getattr(item, "ajustes_totais_brl", 0)) < 0), 2),
            "exchanges": exchange_mtm_rows[:6],
            "worst_exchange": worst_exchange,
        },
        "maturity_story": {
            "body": maturity_body,
            "bullets": maturity_bullets[:4],
        },
        "context": {
            "recent_news_count": len(recent_news),
            "recent_news_titles": [item.titulo for item in recent_news if item.titulo],
            "policy_reference_month": getattr(current_policy, "mes_ano", None).isoformat() if getattr(current_policy, "mes_ano", None) else None,
        },
        "data_quality": {
            "sources": [
                {
                    **item,
                    "status": "ok" if item["count"] > 0 else "missing",
                }
                for item in source_rows
            ]
        },
    }

    local_insights = _build_local_insights(payload)
    payload["dashboard_stories"] = _build_dashboard_stories(payload)
    payload["question_lab"] = _build_question_lab(payload, local_insights)
    ai_result = _call_openai_insights(payload, local_insights)

    response = {
        **payload,
        "local_insights": local_insights,
        "written_cards": _build_written_cards(payload, local_insights),
        "ai_enabled": bool(getattr(settings, "OPENAI_API_KEY", "")),
        "ai_result": ai_result["parsed"] if ai_result else None,
        "ai_model": ai_result["model"] if ai_result else None,
    }
    return response
