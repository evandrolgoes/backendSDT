from rest_framework import serializers

from apps.core.serializers import PrivacyScopedSerializerMixin

from .models import ActualCost, BudgetCost, CashPayment, PhysicalPayment, PhysicalQuote, PhysicalSale


class PhysicalQuoteSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = PhysicalQuote
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class BudgetCostSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = BudgetCost
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class ActualCostSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ActualCost
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class PhysicalSaleSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = PhysicalSale
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by", "faturamento_total_contrato"]


class PhysicalPaymentSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = PhysicalPayment
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class CashPaymentSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = CashPayment
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]
