from apps.core.viewsets import TenantScopedModelViewSet

from .models import ExposurePosition
from .serializers import ExposurePositionSerializer


class ExposurePositionViewSet(TenantScopedModelViewSet):
    queryset = ExposurePosition.objects.select_related("tenant", "client", "group", "subgroup", "crop", "season").all()
    serializer_class = ExposurePositionSerializer
    filterset_fields = ["tenant", "client", "group", "subgroup", "crop", "season", "reference_date"]
