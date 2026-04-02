from rest_framework import serializers

from apps.core.serializers import PrivacyScopedSerializerMixin

from .models import ExposurePosition


class ExposurePositionSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ExposurePosition
        fields = "__all__"
