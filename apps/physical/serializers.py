from rest_framework import serializers

from .models import HedgeAllocation, PhysicalSale
from .services import calculate_gross_values


class PhysicalSaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhysicalSale
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]

    def create(self, validated_data):
        brl, usd = calculate_gross_values(
            validated_data.get("price"),
            validated_data.get("quantity"),
            validated_data.get("exchange_rate"),
        )
        validated_data.setdefault("gross_value_brl", brl)
        validated_data.setdefault("gross_value_usd", usd)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        brl, usd = calculate_gross_values(
            validated_data.get("price", instance.price),
            validated_data.get("quantity", instance.quantity),
            validated_data.get("exchange_rate", instance.exchange_rate),
        )
        validated_data["gross_value_brl"] = brl
        validated_data["gross_value_usd"] = usd
        return super().update(instance, validated_data)


class HedgeAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = HedgeAllocation
        fields = "__all__"
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        request = self.context["request"]
        if request.user.is_superuser:
            return attrs

        physical_sale = attrs.get("physical_sale") or getattr(self.instance, "physical_sale", None)
        derivative_operation = attrs.get("derivative_operation") or getattr(self.instance, "derivative_operation", None)
        allocated_unit = attrs.get("allocated_unit") or getattr(self.instance, "allocated_unit", None)
        tenant = request.user.tenant

        if physical_sale and physical_sale.tenant_id != tenant.id:
            raise serializers.ValidationError("A venda fisica nao pertence ao tenant autenticado.")
        if derivative_operation and derivative_operation.tenant_id != tenant.id:
            raise serializers.ValidationError("A operacao derivativa nao pertence ao tenant autenticado.")
        if attrs.get("tenant") and attrs["tenant"] != tenant:
            raise serializers.ValidationError("Nao e permitido alocar registros para outro tenant.")
        if allocated_unit is None:
            raise serializers.ValidationError("A unidade alocada e obrigatoria.")
        return attrs
