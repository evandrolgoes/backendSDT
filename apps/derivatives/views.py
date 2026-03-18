from apps.core.viewsets import TenantScopedModelViewSet

from .models import DerivativeOperation
from .serializers import DerivativeOperationSerializer


class DerivativeOperationViewSet(TenantScopedModelViewSet):
    queryset = DerivativeOperation.objects.select_related(
        "tenant", "subgrupo", "grupo", "cultura", "safra", "contraparte", "created_by"
    ).all()
    serializer_class = DerivativeOperationSerializer
    filterset_fields = ["tenant", "subgrupo", "grupo", "cultura", "safra", "contraparte", "compra_venda", "tipo_derivativo"]
    search_fields = ["cod_operacao_mae", "contrato_derivativo", "nome_da_operacao"]
