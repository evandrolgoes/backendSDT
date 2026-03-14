from rest_framework import serializers

from .models import Broker, ClientAccount, Counterparty, CropSeason, EconomicGroup, SubGroup


class TenantScopedSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request:
            return
        if "tenant" in self.fields and not request.user.is_superuser:
            self.fields["tenant"].required = False
            self.fields["tenant"].read_only = True

    def validate_tenant(self, value):
        request = self.context["request"]
        return value if request.user.is_superuser else request.user.tenant

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        if request and not request.user.is_superuser and "tenant" in self.fields:
            attrs["tenant"] = request.user.tenant
        return attrs


class ClientAccountSerializer(TenantScopedSerializer):
    class Meta:
        model = ClientAccount
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class EconomicGroupSerializer(TenantScopedSerializer):
    class Meta:
        model = EconomicGroup
        fields = "__all__"


class SubGroupSerializer(TenantScopedSerializer):
    class Meta:
        model = SubGroup
        fields = "__all__"


class CropSeasonSerializer(TenantScopedSerializer):
    class Meta:
        model = CropSeason
        fields = "__all__"


class CounterpartySerializer(TenantScopedSerializer):
    class Meta:
        model = Counterparty
        fields = "__all__"


class BrokerSerializer(TenantScopedSerializer):
    class Meta:
        model = Broker
        fields = "__all__"
