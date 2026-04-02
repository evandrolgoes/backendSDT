from django.db.models import Q


GROUP_MODEL_LABEL = "clients.economicgroup"
SUBGROUP_MODEL_LABEL = "clients.subgroup"


def _is_privacy_exempt(user):
    return not getattr(user, "is_authenticated", False) or getattr(user, "is_superuser", False)


def _normalize_allowed_values(values):
    return {str(value) for value in values if value not in (None, "")}


def _get_relation_model_label(field):
    related_model = getattr(field, "related_model", None) or getattr(getattr(field, "remote_field", None), "model", None)
    if related_model is None:
        return None
    meta = getattr(related_model, "_meta", None)
    if meta is None:
        return None
    return meta.label_lower


def get_user_privacy_scope(user):
    cached = getattr(user, "_privacy_scope_cache", None)
    if cached is not None:
        return cached

    if _is_privacy_exempt(user):
        scope = {
            "enabled": False,
            "group_ids": set(),
            "subgroup_ids": set(),
            "group_values": set(),
            "subgroup_values": set(),
        }
        setattr(user, "_privacy_scope_cache", scope)
        return scope

    group_ids = set(user.accessible_groups.values_list("id", flat=True))
    subgroup_rows = list(
        user.accessible_subgroups.values_list("id", "grupo_id")
    )
    subgroup_ids = {subgroup_id for subgroup_id, _group_id in subgroup_rows}
    group_ids.update(group_id for _subgroup_id, group_id in subgroup_rows if group_id)

    scope = {
        "enabled": True,
        "group_ids": group_ids,
        "subgroup_ids": subgroup_ids,
        "group_values": _normalize_allowed_values(group_ids),
        "subgroup_values": _normalize_allowed_values(subgroup_ids),
    }
    setattr(user, "_privacy_scope_cache", scope)
    return scope


def get_accessible_group_queryset(user):
    from apps.clients.models import EconomicGroup

    scope = get_user_privacy_scope(user)
    queryset = EconomicGroup.objects.all().order_by("grupo", "id")
    if not scope["enabled"]:
        return queryset
    return queryset.filter(id__in=scope["group_ids"])


def get_accessible_subgroup_queryset(user):
    from apps.clients.models import SubGroup

    scope = get_user_privacy_scope(user)
    queryset = SubGroup.objects.select_related("grupo").all().order_by("grupo__grupo", "subgrupo", "id")
    if not scope["enabled"]:
        return queryset
    return queryset.filter(id__in=scope["subgroup_ids"])


def get_group_privacy_field_names(model):
    return tuple(
        field.name
        for field in model._meta.get_fields()
        if getattr(field, "is_relation", False)
        and not getattr(field, "auto_created", False)
        and _get_relation_model_label(field) == GROUP_MODEL_LABEL
    )


def get_subgroup_privacy_field_names(model):
    return tuple(
        field.name
        for field in model._meta.get_fields()
        if getattr(field, "is_relation", False)
        and not getattr(field, "auto_created", False)
        and _get_relation_model_label(field) == SUBGROUP_MODEL_LABEL
    )


def _build_allowed_relation_q(model, field_names, allowed_ids):
    predicate = Q()
    for field_name in field_names:
        field = model._meta.get_field(field_name)
        lookup = f"{field_name}__id__in" if getattr(field, "many_to_many", False) else f"{field_name}_id__in"
        predicate |= Q(**{lookup: list(allowed_ids)})
    return predicate


def _build_empty_relation_q(model, field_names):
    predicate = Q()
    for field_name in field_names:
        field = model._meta.get_field(field_name)
        lookup = f"{field_name}__isnull"
        if getattr(field, "many_to_many", False):
            predicate &= Q(**{lookup: True})
        else:
            predicate &= Q(**{lookup: True})
    return predicate


def apply_group_privacy_scope(queryset, user, group_fields=(), subgroup_fields=()):
    scope = get_user_privacy_scope(user)
    if not scope["enabled"]:
        return queryset

    model = queryset.model
    model_label = model._meta.label_lower
    if model_label == GROUP_MODEL_LABEL:
        return queryset.filter(id__in=scope["group_ids"])
    if model_label == SUBGROUP_MODEL_LABEL:
        return queryset.filter(id__in=scope["subgroup_ids"])

    group_fields = tuple(group_fields or get_group_privacy_field_names(model))
    subgroup_fields = tuple(subgroup_fields or get_subgroup_privacy_field_names(model))

    if not group_fields and not subgroup_fields:
        return queryset

    conditions = []
    if subgroup_fields and scope["subgroup_ids"]:
        conditions.append(_build_allowed_relation_q(model, subgroup_fields, scope["subgroup_ids"]))

    if group_fields and scope["group_ids"]:
        group_condition = _build_allowed_relation_q(model, group_fields, scope["group_ids"])
        if subgroup_fields:
            group_condition &= _build_empty_relation_q(model, subgroup_fields)
        conditions.append(group_condition)

    if not conditions:
        return queryset.none()

    predicate = conditions[0]
    for condition in conditions[1:]:
        predicate |= condition
    return queryset.filter(predicate).distinct()


def sanitize_dashboard_filter(user, dashboard_filter):
    data = dashboard_filter if isinstance(dashboard_filter, dict) else {}
    scope = get_user_privacy_scope(user)
    if not scope["enabled"]:
        return {
            "grupo": [str(item) for item in (data.get("grupo") or []) if item not in (None, "")],
            "subgrupo": [str(item) for item in (data.get("subgrupo") or []) if item not in (None, "")],
            "cultura": [str(item) for item in (data.get("cultura") or []) if item not in (None, "")],
            "safra": [str(item) for item in (data.get("safra") or []) if item not in (None, "")],
            "localidade": [str(item) for item in (data.get("localidade") or []) if item not in (None, "")],
        }

    return {
        "grupo": [str(item) for item in (data.get("grupo") or []) if str(item) in scope["group_values"]],
        "subgrupo": [str(item) for item in (data.get("subgrupo") or []) if str(item) in scope["subgroup_values"]],
        "cultura": [str(item) for item in (data.get("cultura") or []) if item not in (None, "")],
        "safra": [str(item) for item in (data.get("safra") or []) if item not in (None, "")],
        "localidade": [str(item) for item in (data.get("localidade") or []) if item not in (None, "")],
    }
