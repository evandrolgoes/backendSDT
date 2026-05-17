from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.viewsets import TenantScopedModelViewSet
from .models import (
    BasisSeries,
    ConabBasisSnapshot,
    ForwardCoverageSnapshot,
    FxRate,
    MarketPrice,
    SojaCrushSnapshot,
)
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
    filterset_fields = ["crop", "region", "source", "basis_date"]


class ConabBasisDatasetView(APIView):
    """Último snapshot do dataset sazonal de basis (CONAB + CBOT + PTAX).

    Público (a página Basis 2 é pública). Se ainda não houver snapshot,
    devolve 204 — o front cai no dataset embutido (fallback) sem quebrar.
    """

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        snapshot = ConabBasisSnapshot.objects.order_by("-updated_at").first()
        if snapshot is None:
            return Response(status=204)
        return Response(snapshot.payload)


class SojaCrushDatasetView(APIView):
    """Último snapshot de esmagamento/cobertura das fábricas de soja.

    Público (a página é pública). Sem snapshot ainda → 204; o front mostra
    um estado vazio orientando a rodar o coletor.
    """

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        snapshot = SojaCrushSnapshot.objects.order_by("-updated_at").first()
        if snapshot is None:
            return Response(status=204)
        return Response(snapshot.payload)


class ForwardCoverageDatasetView(APIView):
    """Último snapshot de cobertura forward das fábricas (SAFRAS + Kpler).

    Público. Sem snapshot → 204. Com snapshot, o payload sempre traz o
    status de cada provedor (inclusive "not_configured"); o front decide
    mostrar gráfico ou placeholder de "conectar provedor".
    """

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        snapshot = ForwardCoverageSnapshot.objects.order_by("-updated_at").first()
        if snapshot is None:
            return Response(status=204)
        return Response(snapshot.payload)

