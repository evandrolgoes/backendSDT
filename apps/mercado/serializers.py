import json
import re

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


def build_html_excerpt(value, max_length=220):
    plain_text = re.sub(r"<style[\s\S]*?</style>|<script[\s\S]*?</script>|<[^>]+>", " ", str(value or ""), flags=re.IGNORECASE)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()
    if len(plain_text) <= max_length:
        return plain_text
    return f"{plain_text[: max_length - 3].rstrip()}..."


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


class MarketNewsPostListSerializer(serializers.ModelSerializer):
    published_by_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()

    class Meta:
        model = MarketNewsPost
        fields = [
            "id",
            "titulo",
            "categorias",
            "status_artigo",
            "data_publicacao",
            "published_by_name",
            "created_by_name",
            "created_at",
            "updated_at",
            "audio",
            "excerpt",
        ]

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

    def get_excerpt(self, obj):
        return build_html_excerpt(getattr(obj, "conteudo_html", ""))
