from datetime import date, datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers, viewsets


class TenantScopedModelViewSet(viewsets.ModelViewSet):
    tenant_field = "tenant"

    def _normalize_log_value(self, value):
        if value is None:
            return None
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, bool):
            return value
        return str(value)

    def _serialize_instance_for_log(self, instance):
        data = {}

        for field in instance._meta.fields:
            if field.name in {"created_at", "updated_at"}:
                continue
            value = getattr(instance, field.name, None)
            if field.is_relation and value is not None:
                data[field.name] = str(value)
            else:
                data[field.name] = self._normalize_log_value(value)

        for field in instance._meta.many_to_many:
            data[field.name] = list(getattr(instance, field.name).all().values_list("pk", flat=True))

        return data

    def _build_log_changes(self, before, after):
        keys = sorted(set(before.keys()) | set(after.keys()))
        changes = []
        for key in keys:
            previous = before.get(key)
            current = after.get(key)
            if previous != current:
                changes.append({"campo": key, "de": previous, "para": current})
        return changes

    def _build_log_description(self, action, formulario, changes):
        if not changes:
            return f"{formulario}: {action} sem alteracoes identificadas."

        if action == "criado":
            prefix = f"{formulario}: criado com os valores"
            details = ", ".join(f"{change['campo']}: {change['para']}" for change in changes)
            return f"{prefix} {details}."

        if action == "excluido":
            prefix = f"{formulario}: excluido com os valores"
            details = ", ".join(f"{change['campo']}: {change['de']}" for change in changes)
            return f"{prefix} {details}."

        details = ", ".join(
            f"{change['campo']}: alterado de {change['de']} para {change['para']}"
            for change in changes
        )
        return f"{formulario}: {details}."

    def _create_audit_log(self, action, instance, before=None, after=None):
        from apps.auditing.models import Attachment, AuditLog

        if isinstance(instance, (AuditLog, Attachment)):
            return

        before = before or {}
        after = after or {}
        changes = self._build_log_changes(before, after)
        user = self.request.user if self.request.user.is_authenticated else None
        tenant = getattr(instance, "tenant", None) or getattr(user, "tenant", None)

        if tenant is None:
            return

        formulario = instance._meta.verbose_name.title()
        AuditLog.objects.create(
            tenant=tenant,
            user=user,
            formulario=formulario,
            content_type=ContentType.objects.get_for_model(instance.__class__),
            object_id=instance.pk,
            action=action,
            alteracoes=changes,
            changes_json={"before": before, "after": after},
            description=self._build_log_description(action, formulario, changes),
        )

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
        user = self.request.user
        if user.is_superuser:
            return queryset
        if hasattr(queryset.model, self.tenant_field):
            return queryset.filter(**{self.tenant_field: user.tenant})
        return queryset

    def perform_create(self, serializer):
        extra = {}
        model = serializer.Meta.model
        if hasattr(model, "tenant"):
            if not self.request.user.tenant_id:
                raise serializers.ValidationError({"tenant": "O usuario autenticado nao possui tenant vinculado."})
            extra["tenant"] = self.request.user.tenant
        if hasattr(model, "created_by"):
            extra["created_by"] = self.request.user
        instance = serializer.save(**extra)
        self._create_audit_log("criado", instance, before={}, after=self._serialize_instance_for_log(instance))

    def perform_update(self, serializer):
        before = self._serialize_instance_for_log(serializer.instance)
        instance = serializer.save()
        self._create_audit_log("alterado", instance, before=before, after=self._serialize_instance_for_log(instance))

    def perform_destroy(self, instance):
        before = self._serialize_instance_for_log(instance)
        self._create_audit_log("excluido", instance, before=before, after={})
        instance.delete()
