from rest_framework import serializers

from .models import GoogleCalendarConfig


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
