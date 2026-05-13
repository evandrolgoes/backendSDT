from rest_framework import serializers

from apps.core.serializers import PrivacyScopedSerializerMixin

from .models import CashBalance


class CashBalanceSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = CashBalance
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]
