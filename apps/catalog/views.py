from rest_framework import permissions, viewsets

from apps.core.permissions import IsMasterAdmin

from .models import Crop, Currency, Exchange, MarketInstrument, PriceSource, PriceUnit, Unit
from .serializers import (
    CropSerializer,
    CurrencySerializer,
    ExchangeSerializer,
    MarketInstrumentSerializer,
    PriceSourceSerializer,
    PriceUnitSerializer,
    UnitSerializer,
)


class AdminWriteCatalogPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return IsMasterAdmin().has_permission(request, view)


class CropViewSet(viewsets.ModelViewSet):
    queryset = Crop.objects.all()
    serializer_class = CropSerializer
    permission_classes = [AdminWriteCatalogPermission]
    search_fields = ["cultura"]


class MarketInstrumentViewSet(viewsets.ModelViewSet):
    queryset = MarketInstrument.objects.all()
    serializer_class = MarketInstrumentSerializer
    permission_classes = [AdminWriteCatalogPermission]
    search_fields = ["code", "name", "underlying", "quote_reference"]


class PriceSourceViewSet(viewsets.ModelViewSet):
    queryset = PriceSource.objects.all()
    serializer_class = PriceSourceSerializer
    permission_classes = [AdminWriteCatalogPermission]
    filterset_fields = ["is_active"]
    search_fields = ["name"]


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = [AdminWriteCatalogPermission]
    search_fields = ["nome"]


class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [AdminWriteCatalogPermission]
    search_fields = ["nome"]


class PriceUnitViewSet(viewsets.ModelViewSet):
    queryset = PriceUnit.objects.all()
    serializer_class = PriceUnitSerializer
    permission_classes = [AdminWriteCatalogPermission]
    search_fields = ["nome"]


class ExchangeViewSet(viewsets.ModelViewSet):
    queryset = Exchange.objects.all()
    serializer_class = ExchangeSerializer
    permission_classes = [AdminWriteCatalogPermission]
    search_fields = ["nome"]
