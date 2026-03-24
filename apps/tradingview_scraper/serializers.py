from rest_framework import serializers

from .models import TradingViewWatchlistQuote


class TradingViewWatchlistQuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradingViewWatchlistQuote
        fields = "__all__"
