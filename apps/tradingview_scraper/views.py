from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import TradingViewWatchlistQuote
from .serializers import TradingViewWatchlistQuoteSerializer
from .services import DEFAULT_TRADINGVIEW_WATCHLIST_URL, TradingViewScraperError, parse_watchlist_id_from_url, sync_watchlist_to_db


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

    @action(detail=False, methods=["post"])
    def sync(self, request):
        source_url = (
            request.data.get("source_url")
            or request.query_params.get("source_url")
            or DEFAULT_TRADINGVIEW_WATCHLIST_URL
        )

        try:
            payload = sync_watchlist_to_db(source_url)
        except TradingViewScraperError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": f"Falha ao sincronizar a watchlist: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                "watchlist_id": payload["watchlist_id"] or parse_watchlist_id_from_url(source_url),
                "watchlist_name": payload["watchlist_name"],
                "symbols_found": payload["symbols_found"],
                "quotes_resolved": payload["quotes_resolved"],
                "synced_at": payload["synced_at"],
            }
        )
