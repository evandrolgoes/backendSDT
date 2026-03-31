from rest_framework import serializers

from apps.core.group_access import resolve_group_subgroup_collections, resolve_group_subgroup_pair
from .models import CropBoard, HedgePolicy, Strategy, StrategyTrigger


class StrategySerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        group = attrs.get("grupo", getattr(self.instance, "grupo", None))
        subgroup = attrs.get("subgrupo", getattr(self.instance, "subgrupo", None))
        resolved_group = resolve_group_subgroup_pair(group, subgroup)
        if resolved_group is not None:
            attrs["grupo"] = resolved_group
        return attrs

    class Meta:
        model = Strategy
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class StrategyTriggerSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        groups = attrs.get("grupos", self.instance.grupos.all() if self.instance else [])
        subgroups = attrs.get("subgrupos", self.instance.subgrupos.all() if self.instance else [])
        attrs["grupos"] = resolve_group_subgroup_collections(groups, subgroups)
        return attrs

    class Meta:
        model = StrategyTrigger
        fields = "__all__"


class HedgePolicySerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        groups = attrs.get("grupos", self.instance.grupos.all() if self.instance else [])
        subgroups = attrs.get("subgrupos", self.instance.subgrupos.all() if self.instance else [])
        attrs["grupos"] = resolve_group_subgroup_collections(groups, subgroups)
        return attrs

    class Meta:
        model = HedgePolicy
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class CropBoardSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        group = attrs.get("grupo", getattr(self.instance, "grupo", None))
        subgroup = attrs.get("subgrupo", getattr(self.instance, "subgrupo", None))
        resolved_group = resolve_group_subgroup_pair(group, subgroup)
        if resolved_group is not None:
            attrs["grupo"] = resolved_group
        return attrs

    class Meta:
        model = CropBoard
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by", "producao_total"]
