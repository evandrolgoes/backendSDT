from rest_framework import serializers

from .models import MarketNewsPost


class MarketNewsPostSerializer(serializers.ModelSerializer):
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

    def update(self, instance, validated_data):
        remove_audio = validated_data.pop("remove_audio", False)
        if remove_audio and getattr(instance, "audio", None):
            instance.audio.delete(save=False)
            instance.audio = None
        return super().update(instance, validated_data)
