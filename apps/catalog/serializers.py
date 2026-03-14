from rest_framework import serializers

from .models import Crop, MarketInstrument, PriceSource, UnitOfMeasure


class CropSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crop
        fields = "__all__"


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = "__all__"


class MarketInstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketInstrument
        fields = "__all__"


class PriceSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceSource
        fields = "__all__"
