import mimetypes

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import TenantAwareModel, TimeStampedModel


class AuditLog(TenantAwareModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    formulario = models.CharField(max_length=150, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    action = models.CharField(max_length=50)
    alteracoes = models.JSONField(default=list, blank=True)
    changes_json = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "created_at"])]


class Attachment(TenantAwareModel, TimeStampedModel):
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="attachments")
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    file = models.FileField(upload_to="attachments/", null=True, blank=True)
    original_name = models.CharField(max_length=255)
    file_blob = models.BinaryField(null=True, blank=True)
    stored_content_type = models.CharField(max_length=120, blank=True)
    stored_size = models.PositiveBigIntegerField(default=0)

    def store_uploaded_file(self, uploaded_file):
        if uploaded_file is None:
            return

        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        payload = uploaded_file.read()
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        self.file_blob = payload
        self.file = None
        self.original_name = self.original_name or getattr(uploaded_file, "name", "") or "arquivo"
        guessed_type = getattr(uploaded_file, "content_type", "") or mimetypes.guess_type(self.original_name)[0] or "application/octet-stream"
        self.stored_content_type = guessed_type
        self.stored_size = getattr(uploaded_file, "size", None) or len(payload or b"")

    @classmethod
    def create_from_upload(cls, *, tenant, uploaded_by, content_type, object_id, uploaded_file):
        attachment = cls(
            tenant=tenant,
            uploaded_by=uploaded_by,
            content_type=content_type,
            object_id=object_id,
            original_name=getattr(uploaded_file, "name", "") or "arquivo",
        )
        attachment.store_uploaded_file(uploaded_file)
        attachment.save()
        return attachment
