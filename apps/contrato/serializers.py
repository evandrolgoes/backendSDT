from rest_framework import serializers

from .models import Contract


class ContractSerializer(serializers.ModelSerializer):
    cliente_name = serializers.CharField(source="cliente.nome", read_only=True)

    class Meta:
        model = Contract
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by", "cliente_name"]
