from apps.core.viewsets import TenantScopedModelViewSet

from .models import Contract
from .serializers import ContractSerializer


class ContractViewSet(TenantScopedModelViewSet):
    queryset = Contract.objects.select_related("tenant", "created_by", "cliente").all()
    serializer_class = ContractSerializer
    filterset_fields = [
        "cliente",
        "frequencia_pagamentos",
        "status_contrato",
        "produto",
        "data_inicio_contrato",
        "data_fim_contrato",
    ]
    search_fields = [
        "cliente__nome",
        "frequencia_pagamentos",
        "status_contrato",
        "produto",
        "descricao",
    ]
    ordering_fields = ["data_inicio_contrato", "data_fim_contrato", "valor_total_contrato", "created_at"]
