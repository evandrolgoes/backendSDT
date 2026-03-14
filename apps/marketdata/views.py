from rest_framework import viewsets

from apps.core.viewsets import TenantScopedModelViewSet
from .models import BasisSeries, FxRate, MarketPrice
from .serializers import BasisSeriesSerializer, FxRateSerializer, MarketPriceSerializer


class MarketPriceViewSet(viewsets.ModelViewSet):
    queryset = MarketPrice.objects.select_related("instrument", "source").all()
    serializer_class = MarketPriceSerializer
    filterset_fields = ["instrument", "source", "price_date"]
    ordering_fields = ["price_date", "price_time"]


class FxRateViewSet(viewsets.ModelViewSet):
    queryset = FxRate.objects.all()
    serializer_class = FxRateSerializer
    filterset_fields = ["base_currency", "quote_currency", "rate_date"]
    ordering_fields = ["rate_date"]


class BasisSeriesViewSet(TenantScopedModelViewSet):
    queryset = BasisSeries.objects.select_related("tenant", "crop", "source").all()
    serializer_class = BasisSeriesSerializer
    filterset_fields = ["tenant", "crop", "region", "source", "basis_date"]
