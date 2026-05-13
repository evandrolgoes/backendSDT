from apps.core.viewsets import TenantScopedModelViewSet

from .models import CashBalance
from .serializers import CashBalanceSerializer


class CashBalanceViewSet(TenantScopedModelViewSet):
    queryset = CashBalance.objects.select_related("tenant", "grupo", "subgrupo", "created_by").all()
    serializer_class = CashBalanceSerializer
    filterset_fields = ["grupo", "subgrupo", "moeda", "considerar_no_fluxo", "banco"]
    search_fields = ["conta", "banco", "obs", "grupo__grupo", "subgrupo__subgrupo", "moeda"]
