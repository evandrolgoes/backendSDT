from rest_framework import serializers

from apps.core.serializers import PrivacyScopedSerializerMixin

from .models import CropBoard, HedgePolicy, Strategy, StrategyTrigger


class StrategySerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Strategy
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class StrategyTriggerSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = StrategyTrigger
        fields = "__all__"


class HedgePolicySerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = HedgePolicy
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class CropBoardSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = CropBoard
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by", "producao_total"]
