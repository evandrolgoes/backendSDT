from rest_framework import serializers, viewsets

from apps.auditing.context import suppress_audit_signals
from apps.auditing.models import Attachment, AuditLog
from apps.auditing.services import build_log_changes, build_log_description, create_audit_log, normalize_log_value, serialize_instance_for_log
from apps.core.privacy import apply_group_privacy_scope


class TenantScopedModelViewSet(viewsets.ModelViewSet):
    tenant_field = "tenant"

    def _normalize_log_value(self, value):
        return normalize_log_value(value)

    def _serialize_instance_for_log(self, instance):
        return serialize_instance_for_log(instance)

    def _build_log_changes(self, before, after):
        return build_log_changes(before, after)

    def _build_log_description(self, action, formulario, changes):
        return build_log_description(action, formulario, changes)

    def _create_audit_log(self, action, instance, before=None, after=None):
        if isinstance(instance, (AuditLog, Attachment)):
            return

        user = self.request.user if self.request.user.is_authenticated else None
        create_audit_log(action, instance, before=before, after=after, user=user)

    def get_serializer(self, *args, **kwargs):
        data = kwargs.get("data")
        serializer_class = self.get_serializer_class()
        model = getattr(getattr(serializer_class, "Meta", None), "model", None)

        if data is not None and model is not None and hasattr(model, self.tenant_field) and getattr(self.request.user, "tenant_id", None):
            mutable_data = data.copy() if hasattr(data, "copy") else dict(data)
            if not mutable_data.get(self.tenant_field):
                mutable_data[self.tenant_field] = self.request.user.tenant_id
            kwargs["data"] = mutable_data

        return super().get_serializer(*args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        user = getattr(self.request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return queryset.none()
        return apply_group_privacy_scope(queryset, user)

    def perform_create(self, serializer):
        extra = {}
        model = serializer.Meta.model
        if hasattr(model, "tenant"):
            if not self.request.user.tenant_id:
                raise serializers.ValidationError({"tenant": "O usuario autenticado nao possui tenant vinculado."})
            extra["tenant"] = self.request.user.tenant
        if hasattr(model, "created_by"):
            extra["created_by"] = self.request.user
        with suppress_audit_signals():
            instance = serializer.save(**extra)
        self._create_audit_log("criado", instance, before={}, after=self._serialize_instance_for_log(instance))

    def perform_update(self, serializer):
        before = self._serialize_instance_for_log(serializer.instance)
        with suppress_audit_signals():
            instance = serializer.save()
        self._create_audit_log("alterado", instance, before=before, after=self._serialize_instance_for_log(instance))

    def perform_destroy(self, instance):
        before = self._serialize_instance_for_log(instance)
        self._create_audit_log("excluido", instance, before=before, after={})
        with suppress_audit_signals():
            instance.delete()
