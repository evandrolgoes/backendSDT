from apps.core.viewsets import TenantScopedModelViewSet

from .models import CropBoard, HedgePolicy, Strategy, StrategyTrigger
from .serializers import CropBoardSerializer, HedgePolicySerializer, StrategySerializer, StrategyTriggerSerializer


class StrategyViewSet(TenantScopedModelViewSet):
    queryset = Strategy.objects.select_related("tenant", "grupo", "subgrupo", "created_by").all()
    serializer_class = StrategySerializer
    filterset_fields = ["tenant", "grupo", "subgrupo", "status"]
    search_fields = ["descricao_estrategia", "obs", "status"]


class StrategyTriggerViewSet(TenantScopedModelViewSet):
    queryset = StrategyTrigger.objects.select_related("estrategia", "cultura").prefetch_related("grupos", "subgrupos").all()
    serializer_class = StrategyTriggerSerializer
    filterset_fields = ["estrategia", "cultura", "status_gatilho", "tipo_fis_der", "posicao"]
    search_fields = ["contrato_bolsa", "codigo_derivativo", "produto_bolsa", "status"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(estrategia__tenant=self.request.user.tenant)


class HedgePolicyViewSet(TenantScopedModelViewSet):
    queryset = HedgePolicy.objects.select_related("tenant", "cultura", "safra", "created_by").prefetch_related("grupos", "subgrupos").all()
    serializer_class = HedgePolicySerializer
    filterset_fields = ["tenant", "cultura", "safra"]
    search_fields = ["obs"]


class CropBoardViewSet(TenantScopedModelViewSet):
    queryset = CropBoard.objects.select_related("tenant", "cultura", "safra", "created_by").prefetch_related("grupos", "subgrupos").all()
    serializer_class = CropBoardSerializer
    filterset_fields = ["tenant", "cultura", "safra", "monitorar_vc", "criar_politica_hedge"]
    search_fields = ["obs", "bolsa_ref", "unidade_producao"]
