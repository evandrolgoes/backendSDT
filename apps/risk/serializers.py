from rest_framework import serializers

from .models import ExposurePosition


class ExposurePositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExposurePosition
        fields = "__all__"
