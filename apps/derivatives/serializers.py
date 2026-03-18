from rest_framework import serializers

from .models import DerivativeOperation


class DerivativeOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DerivativeOperation
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]
