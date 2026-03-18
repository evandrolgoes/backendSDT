from rest_framework import serializers

from .models import ActualCost, BudgetCost, CashPayment, PhysicalPayment, PhysicalQuote, PhysicalSale


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
        read_only_fields = ["created_at", "updated_at", "created_by", "faturamento_total_contrato"]


class PhysicalPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhysicalPayment
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class CashPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashPayment
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]
