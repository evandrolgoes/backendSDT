from apps.core.viewsets import TenantScopedModelViewSet

from .models import AccountsPayable
from .serializers import AccountsPayableSerializer


class AccountsPayableViewSet(TenantScopedModelViewSet):
    queryset = AccountsPayable.objects.select_related("tenant", "created_by").all()
    serializer_class = AccountsPayableSerializer
    filterset_fields = ["empresa", "forma_pagamento", "status", "data_pagamento", "data_vencimento"]
    search_fields = ["empresa", "forma_pagamento", "obs", "referencia", "status"]
