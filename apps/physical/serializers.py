from rest_framework import serializers

from apps.core.group_access import resolve_group_subgroup_pair
from .models import ActualCost, BudgetCost, CashPayment, PhysicalPayment, PhysicalQuote, PhysicalSale


class GroupSubgroupScopedSerializer(serializers.ModelSerializer):
    group_field_name = "grupo"
    subgroup_field_name = "subgrupo"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        group = attrs.get(self.group_field_name, getattr(self.instance, self.group_field_name, None))
        subgroup = attrs.get(self.subgroup_field_name, getattr(self.instance, self.subgroup_field_name, None))
        resolved_group = resolve_group_subgroup_pair(
            group,
            subgroup,
            group_field_name=self.group_field_name,
            subgroup_field_name=self.subgroup_field_name,
        )
        if resolved_group is not None:
            attrs[self.group_field_name] = resolved_group
        return attrs


class PhysicalQuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhysicalQuote
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class BudgetCostSerializer(GroupSubgroupScopedSerializer):
    class Meta:
        model = BudgetCost
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class ActualCostSerializer(GroupSubgroupScopedSerializer):
    class Meta:
        model = ActualCost
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class PhysicalSaleSerializer(GroupSubgroupScopedSerializer):
    class Meta:
        model = PhysicalSale
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by", "faturamento_total_contrato"]


class PhysicalPaymentSerializer(GroupSubgroupScopedSerializer):
    class Meta:
        model = PhysicalPayment
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class CashPaymentSerializer(GroupSubgroupScopedSerializer):
    class Meta:
        model = CashPayment
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]
