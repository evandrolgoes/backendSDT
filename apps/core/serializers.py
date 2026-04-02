from rest_framework import serializers

from .privacy import (
    GROUP_MODEL_LABEL,
    SUBGROUP_MODEL_LABEL,
    get_accessible_group_queryset,
    get_accessible_subgroup_queryset,
    get_user_privacy_scope,
)


def _field_relation_label(field):
    queryset = getattr(field, "queryset", None)
    if queryset is not None:
        return queryset.model._meta.label_lower

    child_relation = getattr(field, "child_relation", None)
    child_queryset = getattr(child_relation, "queryset", None)
    if child_queryset is not None:
        return child_queryset.model._meta.label_lower

    return None


class PrivacyScopedSerializerMixin(serializers.Serializer):
    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        user = getattr(request, "user", None)
        scope = get_user_privacy_scope(user)
        if not scope["enabled"]:
            return fields

        group_queryset = get_accessible_group_queryset(user)
        subgroup_queryset = get_accessible_subgroup_queryset(user)

        for field in fields.values():
            relation_label = _field_relation_label(field)
            if relation_label == GROUP_MODEL_LABEL:
                if getattr(field, "queryset", None) is not None:
                    field.queryset = group_queryset
                elif getattr(getattr(field, "child_relation", None), "queryset", None) is not None:
                    field.child_relation.queryset = group_queryset
            elif relation_label == SUBGROUP_MODEL_LABEL:
                if getattr(field, "queryset", None) is not None:
                    field.queryset = subgroup_queryset
                elif getattr(getattr(field, "child_relation", None), "queryset", None) is not None:
                    field.child_relation.queryset = subgroup_queryset

        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        scope = get_user_privacy_scope(user)
        if not scope["enabled"]:
            return data

        for field_name, field in self.fields.items():
            if field_name not in data:
                continue
            relation_label = _field_relation_label(field)
            if relation_label == GROUP_MODEL_LABEL:
                if isinstance(data[field_name], list):
                    data[field_name] = [value for value in data[field_name] if str(value) in scope["group_values"]]
                elif data[field_name] not in (None, "") and str(data[field_name]) not in scope["group_values"]:
                    data[field_name] = None
            elif relation_label == SUBGROUP_MODEL_LABEL:
                if isinstance(data[field_name], list):
                    data[field_name] = [value for value in data[field_name] if str(value) in scope["subgroup_values"]]
                elif data[field_name] not in (None, "") and str(data[field_name]) not in scope["subgroup_values"]:
                    data[field_name] = None

        return data
