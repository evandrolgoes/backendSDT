from functools import reduce

from django.db.models import Q
from rest_framework import serializers, viewsets

from apps.auditing.context import suppress_audit_signals
from apps.auditing.models import Attachment, AuditLog
from apps.auditing.services import build_log_changes, build_log_description, create_audit_log, normalize_log_value, serialize_instance_for_log


class TenantScopedModelViewSet(viewsets.ModelViewSet):
    tenant_field = "tenant"
    group_field_candidates = ("grupo", "group", "grupos")
    subgroup_field_candidates = ("subgrupo", "subgroup", "subgrupos")

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
        user = self.request.user
        if user.is_superuser:
            return queryset
        if hasattr(queryset.model, self.tenant_field):
            accessible_tenant_ids = getattr(user, "get_accessible_tenant_ids", lambda: [getattr(user, "tenant_id", None)])()
            queryset = queryset.filter(**{f"{self.tenant_field}_id__in": accessible_tenant_ids})
        return self._filter_queryset_by_assignments(queryset, user)

    def _available_relation_fields(self, model, candidates, related_model_label):
        available = []
        for field_name in candidates:
            try:
                field = model._meta.get_field(field_name)
            except Exception:
                continue
            if not field.is_relation:
                continue
            remote_model = getattr(field, "related_model", None)
            if remote_model and remote_model._meta.label == related_model_label:
                available.append(field_name)
        return available

    def _build_assignment_queries(self, model, field_names, allowed_ids):
        queries = []
        if not allowed_ids:
            return queries
        for field_name in field_names:
            model_field = model._meta.get_field(field_name)
            if model_field.many_to_many:
                queries.append(Q(**{f"{field_name}__id__in": allowed_ids}))
            else:
                queries.append(Q(**{f"{field_name}_id__in": allowed_ids}))
        return queries

    def _filter_queryset_by_assignments(self, queryset, user):
        if getattr(user, "is_distributor_admin", lambda: False)() or getattr(user, "has_tenant_slug", lambda *args: False)("admin"):
            return queryset

        model = queryset.model
        allowed_group_ids = list(user.assigned_groups.values_list("id", flat=True))
        allowed_subgroup_ids = list(user.assigned_subgroups.values_list("id", flat=True))

        if model._meta.label == "clients.EconomicGroup":
            return queryset.filter(id__in=allowed_group_ids) if allowed_group_ids else queryset.none()
        if model._meta.label == "clients.SubGroup":
            return queryset.filter(id__in=allowed_subgroup_ids) if allowed_subgroup_ids else queryset.none()

        group_fields = self._available_relation_fields(model, self.group_field_candidates, "clients.EconomicGroup")
        subgroup_fields = self._available_relation_fields(model, self.subgroup_field_candidates, "clients.SubGroup")

        if not group_fields and not subgroup_fields:
            return queryset

        queries = []
        queries.extend(self._build_assignment_queries(model, group_fields, allowed_group_ids))
        queries.extend(self._build_assignment_queries(model, subgroup_fields, allowed_subgroup_ids))

        if not queries:
            return queryset.none()

        return queryset.filter(reduce(lambda left, right: left | right, queries)).distinct()

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
