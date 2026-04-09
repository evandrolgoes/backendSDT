from rest_framework import serializers

from apps.core.privacy import get_accessible_group_queryset, get_accessible_subgroup_queryset
from apps.clients.models import EconomicGroup, SubGroup

from .models import ClientAgendaEvent, GoogleCalendarConfig


class GoogleCalendarConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleCalendarConfig
        fields = [
            "id",
            "nome",
            "client_id",
            "client_secret",
            "calendar_id",
            "conectada",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["conectada", "created_at", "updated_at"]
        extra_kwargs = {
            "client_secret": {"write_only": True},
        }


class ClientAgendaEventSerializer(serializers.ModelSerializer):
    grupos = serializers.PrimaryKeyRelatedField(many=True, required=False, queryset=EconomicGroup.objects.none())
    subgrupos = serializers.PrimaryKeyRelatedField(many=True, required=False, queryset=SubGroup.objects.none())
    grupo_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        write_only=True,
        source="grupos",
        queryset=EconomicGroup.objects.none(),
    )
    subgrupo_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        write_only=True,
        source="subgrupos",
        queryset=SubGroup.objects.none(),
    )

    class Meta:
        model = ClientAgendaEvent
        fields = [
            "id",
            "tenant",
            "created_by",
            "titulo",
            "descricao",
            "local",
            "participantes",
            "data_inicio",
            "data_fim",
            "hora_inicio",
            "hora_fim",
            "dia_todo",
            "repeticao",
            "repetir_ate",
            "grupos",
            "subgrupos",
            "grupo_ids",
            "subgrupo_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["tenant", "created_by", "created_at", "updated_at"]

    def to_internal_value(self, data):
        mutable_data = data.copy()
        for field_name in ("repetir_ate", "hora_inicio", "hora_fim"):
            if mutable_data.get(field_name) == "":
                mutable_data[field_name] = None
        return super().to_internal_value(mutable_data)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        if actor and getattr(actor, "is_authenticated", False):
            group_queryset = get_accessible_group_queryset(actor).filter(tenant=actor.tenant)
            subgroup_queryset = get_accessible_subgroup_queryset(actor).filter(tenant=actor.tenant)
            fields["grupos"].child_relation.queryset = group_queryset
            fields["subgrupos"].child_relation.queryset = subgroup_queryset
            fields["grupo_ids"].child_relation.queryset = group_queryset
            fields["subgrupo_ids"].child_relation.queryset = subgroup_queryset
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        grupos = attrs.get("grupos")
        subgrupos = attrs.get("subgrupos")
        if self.instance is not None:
            if grupos is None:
                grupos = self.instance.grupos.all()
            if subgrupos is None:
                subgrupos = self.instance.subgrupos.all()
        grupos = list(grupos or [])
        subgrupos = list(subgrupos or [])
        group_ids = {item.id for item in grupos}
        invalid_subgroups = [item.subgrupo for item in subgrupos if item.grupo_id not in group_ids]
        if invalid_subgroups:
            raise serializers.ValidationError({"subgrupos": "Todos os subgrupos precisam pertencer aos grupos selecionados."})
        return attrs
