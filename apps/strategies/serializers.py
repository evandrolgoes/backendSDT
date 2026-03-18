from rest_framework import serializers

from .models import CropBoard, HedgePolicy, Strategy, StrategyTrigger


class StrategySerializer(serializers.ModelSerializer):
    class Meta:
        model = Strategy
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class StrategyTriggerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategyTrigger
        fields = "__all__"


class HedgePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = HedgePolicy
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class CropBoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = CropBoard
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]
