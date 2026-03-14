from rest_framework import permissions, viewsets

from .models import Crop, MarketInstrument, PriceSource, UnitOfMeasure
from .serializers import CropSerializer, MarketInstrumentSerializer, PriceSourceSerializer, UnitOfMeasureSerializer


class CropViewSet(viewsets.ModelViewSet):
    queryset = Crop.objects.all()
    serializer_class = CropSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["code", "name"]


class UnitOfMeasureViewSet(viewsets.ModelViewSet):
    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["code", "name"]


class MarketInstrumentViewSet(viewsets.ModelViewSet):
    queryset = MarketInstrument.objects.all()
    serializer_class = MarketInstrumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["asset_class", "quote_currency"]
    search_fields = ["code", "name", "underlying"]


class PriceSourceViewSet(viewsets.ModelViewSet):
    queryset = PriceSource.objects.all()
    serializer_class = PriceSourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["is_active"]
    search_fields = ["name"]
