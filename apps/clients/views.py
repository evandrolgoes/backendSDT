from apps.core.viewsets import TenantScopedModelViewSet

from .models import Broker, ClientAccount, Counterparty, CropSeason, EconomicGroup, SubGroup
from .serializers import BrokerSerializer, ClientAccountSerializer, CounterpartySerializer, CropSeasonSerializer, EconomicGroupSerializer, SubGroupSerializer


class ClientAccountViewSet(TenantScopedModelViewSet):
    queryset = ClientAccount.objects.select_related("tenant").all()
    serializer_class = ClientAccountSerializer
    filterset_fields = ["tenant", "profile_type", "is_active"]
    search_fields = ["name", "legal_name", "document"]


class EconomicGroupViewSet(TenantScopedModelViewSet):
    queryset = EconomicGroup.objects.select_related("tenant").all()
    serializer_class = EconomicGroupSerializer
    filterset_fields = ["tenant"]
    search_fields = ["grupo"]


class SubGroupViewSet(TenantScopedModelViewSet):
    queryset = SubGroup.objects.select_related("tenant").all()
    serializer_class = SubGroupSerializer
    filterset_fields = ["tenant"]
    search_fields = ["subgrupo"]


class CropSeasonViewSet(TenantScopedModelViewSet):
    queryset = CropSeason.objects.select_related("tenant").all()
    serializer_class = CropSeasonSerializer
    filterset_fields = ["tenant"]
    search_fields = ["safra"]


class CounterpartyViewSet(TenantScopedModelViewSet):
    queryset = Counterparty.objects.select_related("tenant", "grupo", "subgrupo").all()
    serializer_class = CounterpartySerializer
    filterset_fields = ["tenant", "grupo", "subgrupo"]
    search_fields = ["obs"]


class BrokerViewSet(TenantScopedModelViewSet):
    queryset = Broker.objects.select_related("tenant").all()
    serializer_class = BrokerSerializer
    filterset_fields = ["tenant"]
    search_fields = ["name"]
