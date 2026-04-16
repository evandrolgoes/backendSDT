from rest_framework import serializers

from .models import FinancialEntry


class FinancialEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialEntry
        fields = ["id", "grupo", "safra", "scenario", "table", "key", "valor"]
