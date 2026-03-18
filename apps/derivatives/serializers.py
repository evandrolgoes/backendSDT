import re

from rest_framework import serializers

from .models import DerivativeOperation


class DerivativeOperationSerializer(serializers.ModelSerializer):
    def _build_next_operation_code(self, tenant):
        queryset = DerivativeOperation.objects.all()
        if tenant is not None:
            queryset = queryset.filter(tenant=tenant)

        highest_number = 0
        for code in queryset.values_list("cod_operacao_mae", flat=True):
            match = re.search(r"(\d+)$", str(code or "").strip())
            if match:
                highest_number = max(highest_number, int(match.group(1)))

        return f"DRV-{highest_number + 1:03d}"

    def create(self, validated_data):
        if not str(validated_data.get("cod_operacao_mae") or "").strip():
            validated_data["cod_operacao_mae"] = self._build_next_operation_code(validated_data.get("tenant"))
        return super().create(validated_data)

    class Meta:
        model = DerivativeOperation
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]
