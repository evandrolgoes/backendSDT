from rest_framework import serializers

from .models import Strategy, StrategyTrigger, TriggerEvent


class StrategySerializer(serializers.ModelSerializer):
    class Meta:
        model = Strategy
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class StrategyTriggerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategyTrigger
        fields = "__all__"

    def validate(self, attrs):
        request = self.context["request"]
        if request.user.is_superuser:
            return attrs
        strategy = attrs.get("strategy") or getattr(self.instance, "strategy", None)
        if strategy and strategy.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("A estrategia nao pertence ao tenant autenticado.")
        return attrs


class TriggerEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TriggerEvent
        fields = "__all__"

    def validate(self, attrs):
        request = self.context["request"]
        if request.user.is_superuser:
            return attrs
        trigger = attrs.get("trigger") or getattr(self.instance, "trigger", None)
        if trigger and trigger.strategy.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("O gatilho nao pertence ao tenant autenticado.")
        return attrs
