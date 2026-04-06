from apps.core.viewsets import TenantScopedModelViewSet

from .models import OtherCashOutflow
from .serializers import OtherCashOutflowSerializer


class OtherCashOutflowViewSet(TenantScopedModelViewSet):
    queryset = OtherCashOutflow.objects.select_related("tenant", "grupo", "subgrupo", "created_by").all()
    serializer_class = OtherCashOutflowSerializer
    filterset_fields = ["grupo", "subgrupo", "moeda", "status", "data_pagamento"]
    search_fields = ["descricao", "obs", "grupo__grupo", "subgrupo__subgrupo", "moeda", "status"]
