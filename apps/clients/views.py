from rest_framework import response, status
from rest_framework.decorators import action
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.core.viewsets import TenantScopedModelViewSet
from apps.core.permissions import IsMasterAdminOrTenantUser

from .models import Broker, ClientAccount, Counterparty, CropSeason, EconomicGroup, GroupAccessRequest, SubGroup, SubGroupAccessRequest
from .serializers import (
    AccessRequestBulkSerializer,
    BrokerSerializer,
    ClientAccountSerializer,
    CounterpartySerializer,
    CropSeasonSerializer,
    EconomicGroupSerializer,
    GroupAccessRequestSerializer,
    SubGroupAccessRequestSerializer,
    SubGroupSerializer,
    approve_group_access_request,
    approve_subgroup_access_request,
    create_group_access_requests,
    create_subgroup_access_requests,
    reject_group_access_request,
    reject_subgroup_access_request,
)


class ClientAccountViewSet(TenantScopedModelViewSet):
    queryset = ClientAccount.objects.select_related("tenant").all()
    serializer_class = ClientAccountSerializer
    filterset_fields = ["tenant", "profile_type", "is_active"]
    search_fields = ["name", "legal_name", "document"]


class EconomicGroupViewSet(TenantScopedModelViewSet):
    queryset = EconomicGroup.objects.select_related("tenant", "owner").prefetch_related("users_with_access").all()
    serializer_class = EconomicGroupSerializer
    permission_classes = [IsMasterAdminOrTenantUser]
    filterset_fields = ["tenant"]
    search_fields = ["grupo"]

    def get_queryset(self):
        queryset = self.queryset
        user = self.request.user
        if user.is_superuser or getattr(user, "has_tenant_slug", lambda *args: False)("admin"):
            return queryset.distinct()
        return queryset.filter(Q(owner=user) | Q(users_with_access=user)).distinct()

    def _ensure_owner_can_mutate(self, instance):
        user = self.request.user
        if user.is_superuser:
            return
        if instance.owner_id != user.id:
            raise PermissionDenied("Somente o proprietario do grupo pode editar este registro.")

    def perform_update(self, serializer):
        self._ensure_owner_can_mutate(serializer.instance)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._ensure_owner_can_mutate(instance)
        super().perform_destroy(instance)

    @action(detail=False, methods=["post"], url_path="request-access")
    def request_access(self, request):
        serializer = AccessRequestBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = create_group_access_requests(serializer.validated_data["names"], request.user)
        return response.Response(
            {"detail": f"{len(created)} solicitacao(oes) enviada(s)."},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="pending-access-requests")
    def pending_access_requests(self, request):
        queryset = GroupAccessRequest.objects.select_related("requester", "group", "group__owner").filter(
            group__owner=request.user,
            status=GroupAccessRequest.Status.PENDING,
        )
        serializer = GroupAccessRequestSerializer(queryset, many=True)
        return response.Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="approve-access-request")
    def approve_access_request(self, request):
        access_request = GroupAccessRequest.objects.select_related("group", "requester").get(
            pk=request.data.get("request_id"),
            group__owner=request.user,
        )
        approve_group_access_request(access_request, request.user)
        return response.Response({"detail": "Solicitacao aprovada."})

    @action(detail=False, methods=["post"], url_path="reject-access-request")
    def reject_access_request(self, request):
        access_request = GroupAccessRequest.objects.select_related("group", "requester").get(
            pk=request.data.get("request_id"),
            group__owner=request.user,
        )
        reject_group_access_request(access_request, request.user)
        return response.Response({"detail": "Solicitacao rejeitada."})


class SubGroupViewSet(TenantScopedModelViewSet):
    queryset = SubGroup.objects.select_related("tenant", "owner").prefetch_related("users_with_access").all()
    serializer_class = SubGroupSerializer
    permission_classes = [IsMasterAdminOrTenantUser]
    filterset_fields = ["tenant"]
    search_fields = ["subgrupo"]

    def get_queryset(self):
        queryset = self.queryset
        user = self.request.user
        if user.is_superuser or getattr(user, "has_tenant_slug", lambda *args: False)("admin"):
            return queryset.distinct()
        return queryset.filter(Q(owner=user) | Q(users_with_access=user)).distinct()

    def _ensure_owner_can_mutate(self, instance):
        user = self.request.user
        if user.is_superuser:
            return
        if instance.owner_id != user.id:
            raise PermissionDenied("Somente o proprietario do subgrupo pode editar este registro.")

    def perform_update(self, serializer):
        self._ensure_owner_can_mutate(serializer.instance)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._ensure_owner_can_mutate(instance)
        super().perform_destroy(instance)

    @action(detail=False, methods=["post"], url_path="request-access")
    def request_access(self, request):
        serializer = AccessRequestBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = create_subgroup_access_requests(serializer.validated_data["names"], request.user)
        return response.Response(
            {"detail": f"{len(created)} solicitacao(oes) enviada(s)."},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="pending-access-requests")
    def pending_access_requests(self, request):
        queryset = SubGroupAccessRequest.objects.select_related("requester", "subgroup", "subgroup__owner").filter(
            subgroup__owner=request.user,
            status=SubGroupAccessRequest.Status.PENDING,
        )
        serializer = SubGroupAccessRequestSerializer(queryset, many=True)
        return response.Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="approve-access-request")
    def approve_access_request(self, request):
        access_request = SubGroupAccessRequest.objects.select_related("subgroup", "requester").get(
            pk=request.data.get("request_id"),
            subgroup__owner=request.user,
        )
        approve_subgroup_access_request(access_request, request.user)
        return response.Response({"detail": "Solicitacao aprovada."})

    @action(detail=False, methods=["post"], url_path="reject-access-request")
    def reject_access_request(self, request):
        access_request = SubGroupAccessRequest.objects.select_related("subgroup", "requester").get(
            pk=request.data.get("request_id"),
            subgroup__owner=request.user,
        )
        reject_subgroup_access_request(access_request, request.user)
        return response.Response({"detail": "Solicitacao rejeitada."})


class CropSeasonViewSet(TenantScopedModelViewSet):
    queryset = CropSeason.objects.select_related("tenant").all()
    serializer_class = CropSeasonSerializer
    filterset_fields = ["tenant"]
    search_fields = ["safra"]


class CounterpartyViewSet(TenantScopedModelViewSet):
    queryset = Counterparty.objects.select_related("tenant", "grupo", "subgrupo").all()
    serializer_class = CounterpartySerializer
    filterset_fields = ["tenant", "grupo", "subgrupo"]
    search_fields = ["contraparte", "obs"]


class BrokerViewSet(TenantScopedModelViewSet):
    queryset = Broker.objects.select_related("tenant").all()
    serializer_class = BrokerSerializer
    filterset_fields = ["tenant"]
    search_fields = ["name"]
