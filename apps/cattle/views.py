from decimal import Decimal, InvalidOperation

from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.viewsets import TenantScopedModelViewSet

from .models import ConfinementDiet, ConfinementLot
from .serializers import ConfinementDietSerializer, ConfinementLotSerializer
from .services import ConfinementMarginService, MarginInputs


def _dec(value, default=None):
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return default


def _serialize_breakdown(bd):
    return {
        "cenario": bd.cenario,
        "receita_boi": bd.receita_boi,
        "custo_reposicao": bd.custo_reposicao,
        "custo_racao": bd.custo_racao,
        "custo_operacional": bd.custo_operacional,
        "encargos": bd.encargos,
        "custo_total": bd.custo_total,
        "margem_lote": bd.margem_lote,
        "margem_por_arroba": bd.margem_por_arroba,
        "margem_por_cabeca": bd.margem_por_cabeca,
        "margem_pct_custo": bd.margem_pct_custo,
        "racao_milho_hedgeavel": bd.racao_milho_hedgeavel,
        "reposicao_em_aberto": bd.reposicao_em_aberto,
        "avisos": bd.avisos,
    }


class ConfinementDietViewSet(TenantScopedModelViewSet):
    queryset = ConfinementDiet.objects.select_related("tenant", "created_by").all()
    serializer_class = ConfinementDietSerializer
    search_fields = ["nome"]


class ConfinementLotViewSet(TenantScopedModelViewSet):
    queryset = ConfinementLot.objects.select_related(
        "tenant", "cliente", "grupo", "subgrupo", "safra", "ativo", "dieta", "created_by"
    ).all()
    serializer_class = ConfinementLotSerializer
    filterset_fields = ["status", "subgrupo", "safra", "reposicao_status"]
    search_fields = ["codigo_lote", "descricao"]

    @action(detail=True, methods=["get", "post"])
    def margin(self, request, pk=None):
        """Margem do lote (crush): aberta vs travavel.

        Precos externos (BGI/CEPEA/CCM) e custo operacional agregado entram
        via query params/body enquanto os providers nao existem. Ver
        services.ConfinementMarginService (pontos PLUG-*)."""
        lot = self.get_object()
        src = request.data if request.method == "POST" else request.query_params

        inputs = MarginInputs(
            preco_boi_aberto=_dec(src.get("preco_boi_aberto")),
            preco_boi_travavel=_dec(src.get("preco_boi_travavel")),
            base_regional=_dec(src.get("base_regional"), Decimal("0")),
            custo_ms_aberto_brl_kg=_dec(src.get("custo_ms_aberto_brl_kg")),
            custo_ms_travavel_brl_kg=_dec(src.get("custo_ms_travavel_brl_kg")),
            preco_reposicao_aberto=_dec(src.get("preco_reposicao_aberto")),
            custo_operacional_total=_dec(src.get("custo_operacional_total"), Decimal("0")),
            encargos_pct=_dec(src.get("encargos_pct"), Decimal("0")),
        )
        result = ConfinementMarginService(lot, inputs).compute()
        return Response(
            {
                "lote": lot.codigo_lote or lot.id,
                "cabecas": result.cabecas,
                "arrobas_saida_carcaca": result.arrobas_saida_carcaca,
                "arrobas_produzidas": result.arrobas_produzidas,
                "aberta": _serialize_breakdown(result.aberta),
                "travavel": _serialize_breakdown(result.travavel),
            }
        )
