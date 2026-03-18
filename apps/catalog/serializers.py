from rest_framework import serializers

from .models import Crop, Currency, DerivativeOperationName, Exchange, MarketInstrument, PriceSource, PriceUnit, Unit


class CropSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crop
        fields = "__all__"


class MarketInstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketInstrument
        fields = "__all__"


class PriceSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceSource
        fields = "__all__"


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = "__all__"


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = "__all__"


class PriceUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceUnit
        fields = "__all__"


class ExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exchange
        fields = "__all__"


class DerivativeOperationNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = DerivativeOperationName
        fields = "__all__"
