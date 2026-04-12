from rest_framework import serializers


class MissingFieldIgnoredConfigMutationSerializer(serializers.Serializer):
    resource = serializers.CharField(max_length=120)
    field_name = serializers.CharField(max_length=120)

