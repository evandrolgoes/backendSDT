from apps.core.viewsets import TenantScopedModelViewSet

from .models import HedgeAllocation, PhysicalSale
from .serializers import HedgeAllocationSerializer, PhysicalSaleSerializer


class PhysicalSaleViewSet(TenantScopedModelViewSet):
    queryset = PhysicalSale.objects.select_related(
        "tenant", "client", "group", "subgroup", "crop", "season", "counterparty", "unit", "created_by"
    ).all()
    serializer_class = PhysicalSaleSerializer
    filterset_fields = ["tenant", "client", "group", "subgroup", "crop", "season", "status", "counterparty"]
    search_fields = ["external_id", "notes"]
    ordering_fields = ["trade_date", "created_at", "gross_value_brl"]


class HedgeAllocationViewSet(TenantScopedModelViewSet):
    queryset = HedgeAllocation.objects.select_related("tenant", "physical_sale", "derivative_operation", "allocated_unit").all()
    serializer_class = HedgeAllocationSerializer
    filterset_fields = ["tenant", "physical_sale", "derivative_operation", "allocation_type"]
