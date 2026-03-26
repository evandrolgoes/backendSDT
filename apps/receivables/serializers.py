from rest_framework import serializers

from .models import ReceiptEntry


class ReceiptEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiptEntry
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]
