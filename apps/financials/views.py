from decimal import Decimal

from django.db.models import Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Crop
from apps.derivatives.models import DerivativeOperation
from apps.other_cash_outflows.models import OtherCashOutflow
from apps.other_entries.models import OtherEntry
from apps.physical.models import ActualCost, CashPayment, PhysicalSale
from apps.strategies.models import CropBoard

from .models import SCENARIO_CHOICES, FinancialEntry
from .serializers import FinancialEntrySerializer

SCENARIOS = [key for key, _label in SCENARIO_CHOICES]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_ids(request, key):
    """Accept both ?key=1,2 and ?key[]=1&key[]=2 formats."""
    values = []
    for source in (key, f"{key}[]"):
        for item in request.query_params.getlist(source):
            values.extend(part.strip() for part in str(item).split(",") if part.strip())
    return [v for v in values if v]


def _to_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _filter_operational(qs, grupo_ids, subgrupo_ids, cultura_ids, safra_ids,
                         group_field="grupo", sub_field="subgrupo",
                         culture_field="cultura", season_field="safra",
                         has_subgrupo=True, has_cultura=True, has_safra=True):
    if grupo_ids:
        qs = qs.filter(**{f"{group_field}_id__in": grupo_ids})
    if subgrupo_ids and has_subgrupo:
        qs = qs.filter(**{f"{sub_field}_id__in": subgrupo_ids})
    if cultura_ids and has_cultura:
        qs = qs.filter(**{f"{culture_field}_id__in": cultura_ids})
    if safra_ids and has_safra:
        qs = qs.filter(**{f"{season_field}_id__in": safra_ids})
    return qs


# ─── DRE computation ──────────────────────────────────────────────────────────

def _compute_dre_current(tenant, grupo_ids, subgrupo_ids, cultura_ids, safra_ids):
    """
    Aggregate DRE 'Cenário Atual' from operational models.
    Returns a flat dict {key: float|None}.
    """

    def fqs(model, has_subgrupo=True, has_cultura=True, has_safra=True, **extra):
        qs = model.objects.filter(tenant=tenant, **extra)
        return _filter_operational(
            qs, grupo_ids, subgrupo_ids, cultura_ids, safra_ids,
            has_subgrupo=has_subgrupo, has_cultura=has_cultura, has_safra=has_safra,
        )

    # ── Vendas ──
    sales_qs = fqs(PhysicalSale)
    vendas_liquidas = _to_float(
        sales_qs.aggregate(total=Sum("faturamento_total_contrato"))["total"]
    ) or 0.0

    # ── Custos ──
    costs_qs = fqs(ActualCost)
    cmv_raw = _to_float(costs_qs.aggregate(total=Sum("valor"))["total"]) or 0.0
    cmv_total = -cmv_raw  # negative for DRE presentation

    lucro_bruto = vendas_liquidas + cmv_total

    # ── Derivativos: sem subgrupo e sem cultura ──
    deriv_qs = fqs(DerivativeOperation, has_subgrupo=False, has_cultura=False).filter(status_operacao="Encerrado")
    resultado_derivativos = _to_float(
        deriv_qs.aggregate(total=Sum("ajustes_totais_brl"))["total"]
    ) or 0.0

    # ── Outras entradas: sem cultura e sem safra ──
    outras_entradas = _to_float(
        fqs(OtherEntry, has_cultura=False, has_safra=False).aggregate(total=Sum("valor"))["total"]
    ) or 0.0

    # ── Outras saídas: sem cultura e sem safra ──
    outras_saidas_raw = _to_float(
        fqs(OtherCashOutflow, has_cultura=False, has_safra=False).aggregate(total=Sum("valor"))["total"]
    ) or 0.0
    outras_saidas = -outras_saidas_raw

    # ── Empréstimos / Despesas financeiras: sem cultura ──
    cash_qs = fqs(CashPayment, has_cultura=False).filter(status="Pendente")
    despesas_financeiras_raw = _to_float(
        cash_qs.aggregate(total=Sum("valor"))["total"]
    ) or 0.0
    despesas_financeiras = -despesas_financeiras_raw

    resultado_apos_df = (
        lucro_bruto
        + resultado_derivativos
        + outras_entradas
        + outras_saidas
        + despesas_financeiras
    )

    ebitda_total = lucro_bruto  # simplified (sem depreciação/amortização)

    # ── Por cultura ──
    culturas = []
    cropboard_qs = fqs(CropBoard)
    cultura_ids_found = list(set(
        cropboard_qs.exclude(cultura__isnull=True)
        .values_list("cultura_id", flat=True)
    ))

    crop_names = {
        crop.id: crop.ativo or str(crop.id)
        for crop in Crop.objects.filter(id__in=cultura_ids_found)
    }

    for cid in cultura_ids_found:
        cb = fqs(CropBoard).filter(cultura_id=cid)
        s = fqs(PhysicalSale).filter(cultura_id=cid)
        c = fqs(ActualCost).filter(cultura_id=cid)

        producao_total = _to_float(cb.aggregate(Sum("producao_total"))["producao_total__sum"]) or 0
        volume_fisico = _to_float(s.aggregate(Sum("volume_fisico"))["volume_fisico__sum"]) or 0
        faturamento = _to_float(s.aggregate(Sum("faturamento_total_contrato"))["faturamento_total_contrato__sum"]) or 0
        custo_realizado = _to_float(c.aggregate(Sum("valor"))["valor__sum"]) or 0

        preco_medio = round(faturamento / volume_fisico, 2) if volume_fisico else None
        retencao_pct = round(volume_fisico / producao_total * 100, 1) if producao_total else None
        ebitda_pct = round((faturamento - custo_realizado) / faturamento * 100, 1) if faturamento else None

        culturas.append({
            "id": cid,
            "nome": crop_names.get(cid, str(cid)),
            "producao_total": producao_total,
            "volume_fisico": volume_fisico,
            "faturamento": faturamento,
            "custo_realizado": custo_realizado,
            "preco_medio": preco_medio,
            "retencao_pct": retencao_pct,
            "ebitda_pct": ebitda_pct,
        })

    return {
        "summary": {
            "vendas_liquidas": vendas_liquidas or None,
            "cmv_total": cmv_total or None,
            "lucro_bruto": lucro_bruto or None,
            "resultado_derivativos": resultado_derivativos or None,
            "outras_entradas": outras_entradas or None,
            "outras_saidas": outras_saidas or None,
            "despesas_financeiras": despesas_financeiras or None,
            "resultado_apos_df": resultado_apos_df or None,
            "ebitda_total": ebitda_total or None,
        },
        "culturas": culturas,
    }


# ─── Views ────────────────────────────────────────────────────────────────────

class DREBalacoView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_filters(self, request):
        return {
            "grupo_ids": _parse_ids(request, "grupo"),
            "subgrupo_ids": _parse_ids(request, "subgrupo"),
            "cultura_ids": _parse_ids(request, "cultura"),
            "safra_ids": _parse_ids(request, "safra"),
        }

    def _get_stored_entries(self, tenant, grupo_ids, safra_ids):
        """
        Returns stored FinancialEntry values as a nested dict:
          { table: { scenario: { key: valor } } }
        """
        qs = FinancialEntry.objects.filter(tenant=tenant)
        if grupo_ids:
            qs = qs.filter(grupo_id__in=grupo_ids)
        else:
            qs = qs.filter(grupo__isnull=True)
        if safra_ids:
            qs = qs.filter(safra_id__in=safra_ids)
        else:
            qs = qs.filter(safra__isnull=True)

        entries = {}
        for entry in qs:
            entries.setdefault(entry.table, {}).setdefault(entry.scenario, {})[entry.key] = (
                float(entry.valor) if entry.valor is not None else None
            )
        return entries

    def get(self, request):
        tenant = request.user.tenant
        filters = self._get_filters(request)

        dre_current = _compute_dre_current(tenant=tenant, **filters)
        stored = self._get_stored_entries(
            tenant,
            grupo_ids=filters["grupo_ids"],
            safra_ids=filters["safra_ids"],
        )

        return Response({
            "dre_current": dre_current,
            "entries": stored,
        })

    def post(self, request):
        """Upsert a single financial entry."""
        tenant = request.user.tenant

        table = request.data.get("table")
        key = request.data.get("key")
        scenario = request.data.get("scenario", "current")
        grupo_id = request.data.get("grupo") or None
        safra_id = request.data.get("safra") or None
        valor = request.data.get("valor")

        if not table or not key:
            return Response({"error": "table e key são obrigatórios."}, status=400)

        if scenario not in SCENARIOS:
            return Response({"error": f"scenario inválido: {scenario}"}, status=400)

        # Convert valor
        if valor is not None and valor != "":
            try:
                valor = Decimal(str(valor))
            except Exception:
                return Response({"error": "valor inválido."}, status=400)
        else:
            valor = None

        obj, _created = FinancialEntry.objects.update_or_create(
            tenant=tenant,
            grupo_id=grupo_id,
            safra_id=safra_id,
            scenario=scenario,
            table=table,
            key=key,
            defaults={"valor": valor},
        )

        return Response(FinancialEntrySerializer(obj).data, status=200)
