from rest_framework import serializers
from django.utils import timezone
from django.urls import reverse

from .models import Attachment, AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    usuario = serializers.SerializerMethodField()
    created_at_display = serializers.SerializerMethodField()

    def get_usuario(self, obj):
        if not obj.user:
            return ""
        return obj.user.full_name or obj.user.username

    def get_created_at_display(self, obj):
        if not obj.created_at:
            return ""
        localized = timezone.localtime(obj.created_at)
        return localized.strftime("%d/%m/%Y %H:%M")

    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = ["created_at", "created_at_display", "usuario"]


class AttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    def get_file_url(self, obj):
        request = self.context.get("request")
        if getattr(obj, "file_blob", None):
            url = reverse("attachment_content", kwargs={"attachment_id": obj.pk})
            return request.build_absolute_uri(url) if request else url
        if not getattr(obj, "file", None):
            return ""
        try:
            url = obj.file.url
        except ValueError:
            return ""
        return request.build_absolute_uri(url) if request else url

    class Meta:
        model = Attachment
        fields = [
            "id",
            "tenant",
            "uploaded_by",
            "content_type",
            "object_id",
            "file",
            "original_name",
            "created_at",
            "updated_at",
            "file_url",
            "stored_content_type",
            "stored_size",
        ]
        read_only_fields = ["created_at", "updated_at", "uploaded_by", "stored_content_type", "stored_size", "file_url"]
