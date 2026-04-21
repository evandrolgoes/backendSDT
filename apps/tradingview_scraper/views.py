from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.catalog.models import Exchange
from .models import TradingViewWatchlistQuote
from .serializers import TradingViewWatchlistQuoteSerializer
from .services import fetch_continuous_contract_price, sync_auto_contracts


class TradingViewWatchlistQuoteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TradingViewWatchlistQuote.objects.all()
    serializer_class = TradingViewWatchlistQuoteSerializer
    permission_classes = [AllowAny]
    filterset_fields = ["watchlist_id", "watchlist_name", "section_name", "provider", "currency", "instrument_type"]
    search_fields = ["symbol", "ticker", "description", "section_name"]
    ordering_fields = ["sort_order", "symbol", "price", "change_percent", "synced_at"]

    def get_permissions(self):
        if self.action == "sync":
            return [IsAuthenticated()]
        return [permission() for permission in self.permission_classes]

    @action(detail=False, methods=["get"], permission_classes=[AllowAny], url_path="ticker-price")
    def ticker_price(self, request):
        queryset = self.filter_queryset(self.get_queryset()).order_by("sort_order", "ticker")
        payload = [
            {
                "ticker": item.ticker,
                "price": item.price,
            }
            for item in queryset
        ]
        return Response(payload)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny], url_path="historical-price")
    def historical_price(self, request):
        bolsa_ref = request.query_params.get("bolsa_ref", "").strip()
        date_str = request.query_params.get("date", "").strip()
        if not bolsa_ref or not date_str:
            return Response({"error": "bolsa_ref e date são obrigatórios"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            exchange = Exchange.objects.get(nome__iexact=bolsa_ref)
        except Exchange.DoesNotExist:
            return Response({"price": None})
        price = fetch_continuous_contract_price(exchange, date_str)
        return Response({"price": str(price) if price is not None else None})

    @action(detail=False, methods=["post"])
    def sync(self, request):
        try:
            payload = sync_auto_contracts()
        except Exception as exc:
            return Response({"detail": f"Falha ao sincronizar contratos: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                "symbols_generated": payload["symbols_generated"],
                "quotes_resolved": payload["quotes_resolved"],
                "synced_at": payload["synced_at"],
            }
        )
