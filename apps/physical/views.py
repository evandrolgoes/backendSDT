from apps.core.viewsets import TenantScopedModelViewSet

from .models import ActualCost, BudgetCost, PhysicalQuote, PhysicalSale
from .serializers import ActualCostSerializer, BudgetCostSerializer, PhysicalQuoteSerializer, PhysicalSaleSerializer


class PhysicalQuoteViewSet(TenantScopedModelViewSet):
    queryset = PhysicalQuote.objects.select_related("tenant", "safra", "created_by").all()
    serializer_class = PhysicalQuoteSerializer
    filterset_fields = ["tenant", "safra", "data_pgto", "data_report"]
    search_fields = ["cultura_texto", "localidade", "moeda_unidade", "obs"]


class BudgetCostViewSet(TenantScopedModelViewSet):
    queryset = BudgetCost.objects.select_related("tenant", "subgrupo", "grupo", "cultura", "safra", "created_by").all()
    serializer_class = BudgetCostSerializer
    filterset_fields = ["tenant", "subgrupo", "grupo", "cultura", "safra", "considerar_na_politica_de_hedge", "moeda"]
    search_fields = ["grupo_despesa", "obs"]


class ActualCostViewSet(TenantScopedModelViewSet):
    queryset = ActualCost.objects.select_related("tenant", "subgrupo", "grupo", "cultura", "safra", "created_by").all()
    serializer_class = ActualCostSerializer
    filterset_fields = ["tenant", "subgrupo", "grupo", "cultura", "safra", "moeda"]
    search_fields = ["grupo_despesa", "obs"]


class PhysicalSaleViewSet(TenantScopedModelViewSet):
    queryset = PhysicalSale.objects.select_related("tenant", "cultura", "safra", "contraparte", "created_by").prefetch_related("grupos", "subgrupos").all()
    serializer_class = PhysicalSaleSerializer
    filterset_fields = ["tenant", "cultura", "safra", "contraparte", "compra_venda", "moeda_contrato"]
    search_fields = ["contrato_bolsa", "cultura_produto", "objetivo_venda_dolarizada"]
