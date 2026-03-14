from apps.core.viewsets import TenantScopedModelViewSet
from rest_framework import viewsets

from .models import CashSettlement, DerivativeLeg, DerivativeOperation, MarkToMarketSnapshot
from .serializers import CashSettlementSerializer, DerivativeLegSerializer, DerivativeOperationSerializer, MarkToMarketSnapshotSerializer


class DerivativeOperationViewSet(TenantScopedModelViewSet):
    queryset = DerivativeOperation.objects.select_related(
        "tenant", "client", "group", "subgroup", "crop", "season", "broker", "counterparty", "created_by"
    ).all()
    serializer_class = DerivativeOperationSerializer
    filterset_fields = ["tenant", "client", "group", "subgroup", "crop", "season", "broker", "counterparty", "status", "market", "purpose"]
    search_fields = ["strategy_name", "external_id", "notes"]
    ordering_fields = ["trade_date", "created_at"]


class DerivativeLegViewSet(viewsets.ModelViewSet):
    queryset = DerivativeLeg.objects.select_related("operation__tenant", "instrument").all()
    serializer_class = DerivativeLegSerializer
    filterset_fields = ["operation", "instrument", "side", "leg_type", "is_otc"]
    search_fields = ["notes"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(operation__tenant=self.request.user.tenant)


class MarkToMarketSnapshotViewSet(TenantScopedModelViewSet):
    queryset = MarkToMarketSnapshot.objects.select_related("tenant", "derivative_operation").all()
    serializer_class = MarkToMarketSnapshotSerializer
    filterset_fields = ["tenant", "derivative_operation", "snapshot_date", "currency"]


class CashSettlementViewSet(TenantScopedModelViewSet):
    queryset = CashSettlement.objects.select_related("tenant", "derivative_operation").all()
    serializer_class = CashSettlementSerializer
    filterset_fields = ["tenant", "derivative_operation", "settlement_type", "currency"]
