from rest_framework import serializers

from .models import Attachment, AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    usuario = serializers.SerializerMethodField()

    def get_usuario(self, obj):
        if not obj.user:
            return ""
        return obj.user.full_name or obj.user.username

    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = ["created_at", "usuario"]


class AttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    def get_file_url(self, obj):
        if not getattr(obj, "file", None):
            return ""
        try:
            url = obj.file.url
        except ValueError:
            return ""
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    class Meta:
        model = Attachment
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "uploaded_by"]
