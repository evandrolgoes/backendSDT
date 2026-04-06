from apps.core.viewsets import TenantScopedModelViewSet

from .models import EntryClient, ReceiptEntry
from .serializers import EntryClientSerializer, ReceiptEntrySerializer


class EntryClientViewSet(TenantScopedModelViewSet):
    queryset = EntryClient.objects.select_related("tenant").all()
    serializer_class = EntryClientSerializer
    filterset_fields = []
    search_fields = ["nome"]


class ReceiptEntryViewSet(TenantScopedModelViewSet):
    queryset = ReceiptEntry.objects.select_related("tenant", "created_by", "cliente").all()
    serializer_class = ReceiptEntrySerializer
    filterset_fields = ["cliente", "data_recebimento", "data_vencimento", "nf", "status"]
    search_fields = ["cliente__nome", "nf", "produto", "status", "observacoes"]
