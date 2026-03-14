from rest_framework import serializers

from .models import CashSettlement, DerivativeLeg, DerivativeOperation, MarkToMarketSnapshot


class DerivativeOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DerivativeOperation
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class DerivativeLegSerializer(serializers.ModelSerializer):
    class Meta:
        model = DerivativeLeg
        fields = "__all__"

    def validate(self, attrs):
        request = self.context["request"]
        if request.user.is_superuser:
            return attrs
        operation = attrs.get("operation") or getattr(self.instance, "operation", None)
        if operation and operation.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("A operacao informada nao pertence ao tenant autenticado.")
        return attrs


class MarkToMarketSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarkToMarketSnapshot
        fields = "__all__"

    def validate(self, attrs):
        request = self.context["request"]
        if request.user.is_superuser:
            return attrs
        operation = attrs.get("derivative_operation") or getattr(self.instance, "derivative_operation", None)
        if operation and operation.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("A operacao informada nao pertence ao tenant autenticado.")
        return attrs


class CashSettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashSettlement
        fields = "__all__"

    def validate(self, attrs):
        request = self.context["request"]
        if request.user.is_superuser:
            return attrs
        operation = attrs.get("derivative_operation") or getattr(self.instance, "derivative_operation", None)
        if operation and operation.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("A operacao informada nao pertence ao tenant autenticado.")
        return attrs
