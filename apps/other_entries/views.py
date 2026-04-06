from apps.core.viewsets import TenantScopedModelViewSet

from .models import OtherEntry
from .serializers import OtherEntrySerializer


class OtherEntryViewSet(TenantScopedModelViewSet):
    queryset = OtherEntry.objects.select_related("tenant", "grupo", "subgrupo", "created_by").all()
    serializer_class = OtherEntrySerializer
    filterset_fields = ["grupo", "subgrupo", "moeda", "status", "data_entrada"]
    search_fields = ["descricao", "obs", "grupo__grupo", "subgrupo__subgrupo", "moeda", "status"]
