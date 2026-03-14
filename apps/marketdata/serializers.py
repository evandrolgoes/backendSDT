from rest_framework import serializers

from .models import BasisSeries, FxRate, MarketPrice


class MarketPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketPrice
        fields = "__all__"


class FxRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FxRate
        fields = "__all__"


class BasisSeriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = BasisSeries
        fields = "__all__"
