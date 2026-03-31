import json

from rest_framework import serializers

from .models import MarketNewsPost


class CategoryListField(serializers.ListField):
    child = serializers.CharField()

    def to_internal_value(self, data):
        if isinstance(data, str):
            raw = data.strip()
            if not raw:
                data = []
            else:
                try:
                    parsed = json.loads(raw)
                    data = parsed if isinstance(parsed, list) else [parsed]
                except json.JSONDecodeError:
                    data = [item.strip() for item in raw.split(",") if item.strip()]
        return super().to_internal_value(data)


class MarketNewsPostSerializer(serializers.ModelSerializer):
    categorias = CategoryListField(required=False)
    published_by_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    remove_audio = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = MarketNewsPost
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by", "published_by"]

    def validate_categorias(self, value):
        items = []
        seen = set()
        for item in value or []:
            normalized = str(item or "").strip()
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            items.append(normalized)
        return items

    def get_published_by_name(self, obj):
        user = getattr(obj, "published_by", None)
        if not user:
            return ""
        return getattr(user, "full_name", "") or getattr(user, "username", "") or getattr(user, "email", "")

    def get_created_by_name(self, obj):
        user = getattr(obj, "created_by", None)
        if not user:
            return ""
        return getattr(user, "full_name", "") or getattr(user, "username", "") or getattr(user, "email", "")

    def create(self, validated_data):
        validated_data.pop("remove_audio", False)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        remove_audio = validated_data.pop("remove_audio", False)
        if remove_audio and getattr(instance, "audio", None):
            instance.audio.delete(save=False)
            instance.audio = None
        return super().update(instance, validated_data)
