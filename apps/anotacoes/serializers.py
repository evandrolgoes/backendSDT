from rest_framework import serializers

from apps.core.group_access import resolve_group_subgroup_collections
from apps.clients.models import EconomicGroup, SubGroup

from .models import Anotacao


class AnotacaoSerializer(serializers.ModelSerializer):
    grupos = serializers.PrimaryKeyRelatedField(many=True, queryset=EconomicGroup.objects.all(), required=False)
    subgrupos = serializers.PrimaryKeyRelatedField(many=True, queryset=SubGroup.objects.all(), required=False)
    grupos_display = serializers.SerializerMethodField()
    subgrupos_display = serializers.SerializerMethodField()
    modificado_por_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Anotacao
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by", "modificado_por"]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and getattr(request.user, "is_authenticated", False):
            tenant_ids = getattr(request.user, "get_accessible_tenant_ids", lambda: [getattr(request.user, "tenant_id", None)])()
            fields["grupos"].queryset = EconomicGroup.objects.filter(tenant_id__in=tenant_ids).order_by("grupo")
            fields["subgrupos"].queryset = SubGroup.objects.filter(tenant_id__in=tenant_ids).order_by("subgrupo")
        return fields

    def validate_titulo(self, value):
        return str(value or "").strip()

    def validate_participantes(self, value):
        return str(value or "").strip()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        tenant = getattr(self.instance, "tenant", None) or getattr(request.user, "tenant", None)
        if request and not getattr(request.user, "tenant_id", None):
            raise serializers.ValidationError({"tenant": "O usuario autenticado nao possui tenant vinculado."})

        for field_name in ["grupos", "subgrupos"]:
            values = attrs.get(field_name)
            if values is None or tenant is None:
                continue
            invalid = [item.pk for item in values if item.tenant_id != tenant.id]
            if invalid:
                raise serializers.ValidationError({field_name: "Todos os relacionamentos precisam pertencer ao mesmo tenant."})

        groups = attrs.get("grupos", self.instance.grupos.all() if self.instance else [])
        subgroups = attrs.get("subgrupos", self.instance.subgrupos.all() if self.instance else [])
        attrs["grupos"] = resolve_group_subgroup_collections(groups, subgroups)

        return attrs

    def get_grupos_display(self, obj):
        return list(obj.grupos.order_by("grupo").values_list("grupo", flat=True))

    def get_subgrupos_display(self, obj):
        return list(obj.subgrupos.order_by("subgrupo").values_list("subgrupo", flat=True))

    def _user_display(self, user):
        if not user:
            return ""
        return getattr(user, "full_name", "") or getattr(user, "username", "") or getattr(user, "email", "")

    def get_modificado_por_name(self, obj):
        return self._user_display(getattr(obj, "modificado_por", None))

    def get_created_by_name(self, obj):
        return self._user_display(getattr(obj, "created_by", None))
