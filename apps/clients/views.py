from apps.core.viewsets import TenantScopedModelViewSet
from apps.core.permissions import IsMasterAdminOrTenantUser

from .models import Broker, ClientAccount, Counterparty, CropSeason, EconomicGroup, SubGroup
from .serializers import (
    BrokerSerializer,
    ClientAccountSerializer,
    CounterpartySerializer,
    CropSeasonSerializer,
    EconomicGroupSerializer,
    SubGroupSerializer,
)


class ClientAccountViewSet(TenantScopedModelViewSet):
    queryset = ClientAccount.objects.select_related("tenant").all()
    serializer_class = ClientAccountSerializer
    filterset_fields = ["tenant", "profile_type", "is_active"]
    search_fields = ["name", "legal_name", "document"]


class EconomicGroupViewSet(TenantScopedModelViewSet):
    queryset = EconomicGroup.objects.select_related("tenant").all()
    serializer_class = EconomicGroupSerializer
    permission_classes = [IsMasterAdminOrTenantUser]
    group_scope_fields = ("id",)
    filterset_fields = ["tenant"]
    search_fields = ["grupo"]

    def get_queryset(self):
        return super().get_queryset().order_by("grupo", "id").distinct()


class SubGroupViewSet(TenantScopedModelViewSet):
    queryset = SubGroup.objects.select_related("tenant", "grupo").all()
    serializer_class = SubGroupSerializer
    permission_classes = [IsMasterAdminOrTenantUser]
    subgroup_scope_fields = ("id",)
    filterset_fields = ["tenant"]
    search_fields = ["subgrupo"]

    def get_queryset(self):
        return super().get_queryset().order_by("grupo__grupo", "subgrupo", "id").distinct()


class CropSeasonViewSet(TenantScopedModelViewSet):
    queryset = CropSeason.objects.select_related("tenant").all()
    serializer_class = CropSeasonSerializer
    filterset_fields = ["tenant"]
    search_fields = ["safra"]


class CounterpartyViewSet(TenantScopedModelViewSet):
    queryset = Counterparty.objects.select_related("tenant", "grupo").all()
    serializer_class = CounterpartySerializer
    group_scope_fields = ("grupo",)
    filterset_fields = ["tenant", "grupo"]
    search_fields = ["contraparte", "obs"]


class BrokerViewSet(TenantScopedModelViewSet):
    queryset = Broker.objects.select_related("tenant").all()
    serializer_class = BrokerSerializer
    filterset_fields = ["tenant"]
    search_fields = ["name"]
