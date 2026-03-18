from rest_framework import serializers

from .models import ActualCost, BudgetCost, PhysicalQuote, PhysicalSale


class PhysicalQuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhysicalQuote
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class BudgetCostSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetCost
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class ActualCostSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActualCost
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class PhysicalSaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhysicalSale
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]
