from apps.core.viewsets import TenantScopedModelViewSet

from .models import Broker, ClientAccount, Counterparty, CropSeason, EconomicGroup, SubGroup
from .serializers import BrokerSerializer, ClientAccountSerializer, CounterpartySerializer, CropSeasonSerializer, EconomicGroupSerializer, SubGroupSerializer


class ClientAccountViewSet(TenantScopedModelViewSet):
    queryset = ClientAccount.objects.select_related("tenant").all()
    serializer_class = ClientAccountSerializer
    filterset_fields = ["tenant", "profile_type", "is_active"]
    search_fields = ["name", "legal_name", "document"]


class EconomicGroupViewSet(TenantScopedModelViewSet):
    queryset = EconomicGroup.objects.select_related("tenant", "client").all()
    serializer_class = EconomicGroupSerializer
    filterset_fields = ["tenant", "client"]
    search_fields = ["code", "name"]


class SubGroupViewSet(TenantScopedModelViewSet):
    queryset = SubGroup.objects.select_related("tenant", "group").all()
    serializer_class = SubGroupSerializer
    filterset_fields = ["tenant", "group"]
    search_fields = ["code", "name"]


class CropSeasonViewSet(TenantScopedModelViewSet):
    queryset = CropSeason.objects.select_related("tenant", "client", "crop").all()
    serializer_class = CropSeasonSerializer
    filterset_fields = ["tenant", "client", "crop"]
    search_fields = ["season_label"]


class CounterpartyViewSet(TenantScopedModelViewSet):
    queryset = Counterparty.objects.select_related("tenant").all()
    serializer_class = CounterpartySerializer
    filterset_fields = ["tenant", "counterparty_type"]
    search_fields = ["name"]


class BrokerViewSet(TenantScopedModelViewSet):
    queryset = Broker.objects.select_related("tenant").all()
    serializer_class = BrokerSerializer
    filterset_fields = ["tenant"]
    search_fields = ["name"]
