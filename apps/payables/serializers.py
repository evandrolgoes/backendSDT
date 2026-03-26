from rest_framework import serializers

from .models import AccountsPayable


class AccountsPayableSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountsPayable
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]
