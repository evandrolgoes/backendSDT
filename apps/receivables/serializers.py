from rest_framework import serializers

from .models import EntryClient, ReceiptEntry


class EntryClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntryClient
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class ReceiptEntrySerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)

    class Meta:
        model = ReceiptEntry
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]
