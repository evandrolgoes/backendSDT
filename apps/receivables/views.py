from apps.core.viewsets import TenantScopedModelViewSet

from .models import ReceiptEntry
from .serializers import ReceiptEntrySerializer


class ReceiptEntryViewSet(TenantScopedModelViewSet):
    queryset = ReceiptEntry.objects.select_related("tenant", "created_by").all()
    serializer_class = ReceiptEntrySerializer
    filterset_fields = ["tenant", "data_recebimento", "data_vencimento", "status"]
    search_fields = ["cliente", "nf", "produto", "status", "observacoes"]
