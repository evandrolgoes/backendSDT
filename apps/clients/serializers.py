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
    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = attrs.get("tenant", getattr(self.instance, "tenant", None))
        raw_value = attrs.get("grupo", getattr(self.instance, "grupo", None))
        value = (raw_value or "").strip()
        if value:
            attrs["grupo"] = value
            queryset = EconomicGroup.objects.filter(tenant=tenant, grupo__iexact=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({"grupo": "Ja existe um grupo com este nome."})
        return attrs

    class Meta:
        model = EconomicGroup
        fields = ["id", "tenant", "grupo"]


class SubGroupSerializer(TenantScopedSerializer):
    grupo_name = serializers.CharField(source="grupo.grupo", read_only=True)

    def get_fields(self):
        fields = super().get_fields()
        fields["grupo"] = serializers.PrimaryKeyRelatedField(queryset=EconomicGroup.objects.all())
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = attrs.get("tenant", getattr(self.instance, "tenant", None))
        group = attrs.get("grupo", getattr(self.instance, "grupo", None))
        if group is None:
            raise serializers.ValidationError({"grupo": "Selecione o grupo pai do subgrupo."})
        if tenant and group.tenant_id != tenant.id:
            raise serializers.ValidationError({"grupo": "O grupo selecionado precisa pertencer ao mesmo tenant."})

        raw_value = attrs.get("subgrupo", getattr(self.instance, "subgrupo", None))
        value = (raw_value or "").strip()
        if value:
            attrs["subgrupo"] = value
            queryset = SubGroup.objects.filter(tenant=tenant, grupo=group, subgrupo__iexact=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({"subgrupo": "Ja existe um subgrupo com este nome neste grupo."})
        return attrs

    class Meta:
        model = SubGroup
        fields = ["id", "tenant", "grupo", "grupo_name", "subgrupo", "descricao"]


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
