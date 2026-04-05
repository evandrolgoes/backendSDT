from rest_framework import serializers

from apps.core.serializers import PrivacyScopedSerializerMixin

from .models import CropBoard, HedgePolicy, Strategy, StrategyTrigger


class StrategySerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    def _sync_legacy_relations(self, instance, grupos_value, subgrupos_value):
        update_fields = []

        if grupos_value is not serializers.empty:
            instance.grupos.set(grupos_value)
            first_group = grupos_value[0] if grupos_value else None
            if instance.grupo_id != getattr(first_group, "id", None):
                instance.grupo = first_group
                update_fields.append("grupo")
        elif instance.grupo_id and not instance.grupos.exists():
            instance.grupos.set([instance.grupo])

        if subgrupos_value is not serializers.empty:
            instance.subgrupos.set(subgrupos_value)
            first_subgroup = subgrupos_value[0] if subgrupos_value else None
            if instance.subgrupo_id != getattr(first_subgroup, "id", None):
                instance.subgrupo = first_subgroup
                update_fields.append("subgrupo")
        elif instance.subgrupo_id and not instance.subgrupos.exists():
            instance.subgrupos.set([instance.subgrupo])

        if update_fields:
            instance.save(update_fields=update_fields)

    def create(self, validated_data):
        grupos_value = validated_data.pop("grupos", serializers.empty)
        subgrupos_value = validated_data.pop("subgrupos", serializers.empty)

        if grupos_value is not serializers.empty and grupos_value and not validated_data.get("grupo"):
            validated_data["grupo"] = grupos_value[0]
        if subgrupos_value is not serializers.empty and subgrupos_value and not validated_data.get("subgrupo"):
            validated_data["subgrupo"] = subgrupos_value[0]

        instance = super().create(validated_data)
        self._sync_legacy_relations(instance, grupos_value, subgrupos_value)
        return instance

    def update(self, instance, validated_data):
        grupos_value = validated_data.pop("grupos", serializers.empty)
        subgrupos_value = validated_data.pop("subgrupos", serializers.empty)
        grupo_in_payload = "grupo" in validated_data
        subgrupo_in_payload = "subgrupo" in validated_data

        if grupos_value is not serializers.empty:
            validated_data["grupo"] = grupos_value[0] if grupos_value else None
        elif grupo_in_payload:
            grupos_value = [validated_data.get("grupo")] if validated_data.get("grupo") else []

        if subgrupos_value is not serializers.empty:
            validated_data["subgrupo"] = subgrupos_value[0] if subgrupos_value else None
        elif subgrupo_in_payload:
            subgrupos_value = [validated_data.get("subgrupo")] if validated_data.get("subgrupo") else []

        instance = super().update(instance, validated_data)
        self._sync_legacy_relations(instance, grupos_value, subgrupos_value)
        return instance

    class Meta:
        model = Strategy
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class StrategyTriggerSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = StrategyTrigger
        fields = "__all__"


class HedgePolicySerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = HedgePolicy
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class CropBoardSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = CropBoard
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by", "producao_total"]
