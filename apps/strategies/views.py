from rest_framework import viewsets

from apps.core.viewsets import TenantScopedModelViewSet
from .models import Strategy, StrategyTrigger, TriggerEvent
from .serializers import StrategySerializer, StrategyTriggerSerializer, TriggerEventSerializer


class StrategyViewSet(TenantScopedModelViewSet):
    queryset = Strategy.objects.select_related("tenant", "client", "crop", "season", "created_by").all()
    serializer_class = StrategySerializer
    filterset_fields = ["tenant", "client", "crop", "season", "is_active"]
    search_fields = ["name", "description"]


class StrategyTriggerViewSet(viewsets.ModelViewSet):
    queryset = StrategyTrigger.objects.select_related("strategy__tenant").all()
    serializer_class = StrategyTriggerSerializer
    filterset_fields = ["strategy", "trigger_type", "action_type", "is_active"]
    search_fields = ["name", "target_text"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(strategy__tenant=self.request.user.tenant)


class TriggerEventViewSet(viewsets.ModelViewSet):
    queryset = TriggerEvent.objects.select_related("trigger__strategy__tenant").all()
    serializer_class = TriggerEventSerializer
    filterset_fields = ["trigger", "status"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(trigger__strategy__tenant=self.request.user.tenant)
