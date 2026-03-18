from rest_framework import serializers

from .models import Broker, ClientAccount, Counterparty, CropSeason, EconomicGroup, SubGroup


class TenantScopedSerializer(serializers.ModelSerializer):
    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and "tenant" in fields and getattr(request.user, "tenant_id", None):
            fields["tenant"] = serializers.HiddenField(default=request.user.tenant)
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        if request and not request.user.tenant_id:
            raise serializers.ValidationError({"tenant": "O usuario autenticado nao possui tenant vinculado."})
        if request and "tenant" in self.fields and request.user.tenant_id:
            attrs["tenant"] = request.user.tenant
        return attrs

    def validate_tenant(self, value):
        request = self.context["request"]
        return request.user.tenant if request.user.tenant_id else value


class ClientAccountSerializer(TenantScopedSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = attrs.get("tenant") or getattr(self.instance, "tenant", None)
        document = attrs.get("document")

        # The model allows blank documents, so we only enforce uniqueness when a value is provided.
        if tenant and document:
            queryset = ClientAccount.objects.filter(tenant=tenant, document=document)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({"document": "Ja existe um cliente com este documento neste tenant."})

        return attrs

    class Meta:
        model = ClientAccount
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]
        validators = []


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
