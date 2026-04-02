from rest_framework import serializers

from apps.clients.models import EconomicGroup, SubGroup
from apps.core.privacy import get_accessible_group_queryset, get_accessible_subgroup_queryset
from apps.core.serializers import PrivacyScopedSerializerMixin

from .models import Anotacao


class AnotacaoSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
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
        actor = getattr(request, "user", None)
        if actor and getattr(actor, "is_authenticated", False):
            fields["grupos"].queryset = get_accessible_group_queryset(actor)
            fields["subgrupos"].queryset = get_accessible_subgroup_queryset(actor)
        else:
            fields["grupos"].queryset = EconomicGroup.objects.all().order_by("grupo")
            fields["subgrupos"].queryset = SubGroup.objects.all().order_by("subgrupo")
        return fields

    def validate_titulo(self, value):
        return str(value or "").strip()

    def validate_participantes(self, value):
        return str(value or "").strip()

    def validate(self, attrs):
        attrs = super().validate(attrs)
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
