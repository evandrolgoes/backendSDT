from functools import reduce
from operator import or_

from django.db.models import Q
from rest_framework import serializers


def get_user_assignment_scope(user):
    if not getattr(user, "is_authenticated", False):
        return {
            "has_scope": False,
            "direct_group_ids": [],
            "direct_subgroup_ids": [],
            "visible_group_ids": [],
            "visible_subgroup_ids": [],
        }

    direct_group_ids = set(user.assigned_groups.values_list("id", flat=True))
    direct_subgroup_ids = set(user.assigned_subgroups.values_list("id", flat=True))

    if not direct_group_ids and not direct_subgroup_ids:
        return {
            "has_scope": False,
            "direct_group_ids": [],
            "direct_subgroup_ids": [],
            "visible_group_ids": [],
            "visible_subgroup_ids": [],
        }

    from apps.clients.models import SubGroup

    subgroup_parent_group_ids = set(
        SubGroup.objects.filter(id__in=direct_subgroup_ids).values_list("grupo_id", flat=True)
    )
    group_subgroup_ids = set(
        SubGroup.objects.filter(grupo_id__in=direct_group_ids).values_list("id", flat=True)
    )

    visible_group_ids = direct_group_ids | subgroup_parent_group_ids
    visible_subgroup_ids = direct_subgroup_ids | group_subgroup_ids

    return {
        "has_scope": True,
        "direct_group_ids": list(direct_group_ids),
        "direct_subgroup_ids": list(direct_subgroup_ids),
        "visible_group_ids": list(visible_group_ids),
        "visible_subgroup_ids": list(visible_subgroup_ids),
    }


def _build_scope_lookup(model, field_name):
    field = model._meta.get_field(field_name)
    if getattr(field, "many_to_many", False):
        return f"{field_name}__id__in"
    if getattr(field, "is_relation", False):
        return f"{field_name}_id__in"
    return f"{field_name}__in"


def apply_queryset_assignment_scope(queryset, user, *, group_fields=(), subgroup_fields=()):
    if not getattr(user, "is_authenticated", False) or getattr(user, "is_superuser", False):
        return queryset

    scope = get_user_assignment_scope(user)
    if not scope["has_scope"]:
        return queryset.distinct()

    predicates = []
    group_ids = scope["visible_group_ids"]
    subgroup_ids = scope["visible_subgroup_ids"]

    for field_name in group_fields or ():
        if group_ids:
            predicates.append(Q(**{_build_scope_lookup(queryset.model, field_name): group_ids}))

    for field_name in subgroup_fields or ():
        if subgroup_ids:
            predicates.append(Q(**{_build_scope_lookup(queryset.model, field_name): subgroup_ids}))

    if not predicates:
        return queryset.none()

    return queryset.filter(reduce(or_, predicates)).distinct()


def resolve_group_subgroup_pair(group, subgroup, *, group_field_name="grupo", subgroup_field_name="subgrupo"):
    if subgroup is None:
        return group

    subgroup_group = getattr(subgroup, "grupo", None)
    if subgroup_group is None:
        raise serializers.ValidationError(
            {subgroup_field_name: "O subgrupo selecionado precisa estar vinculado a um grupo."}
        )

    if group is None:
        return subgroup_group

    if getattr(group, "id", None) != getattr(subgroup_group, "id", None):
        raise serializers.ValidationError(
            {subgroup_field_name: "O subgrupo selecionado nao pertence ao grupo informado."}
        )

    return group


def resolve_group_subgroup_collections(groups, subgroups, *, group_field_name="grupos", subgroup_field_name="subgrupos"):
    groups = [item for item in (groups or []) if item is not None]
    subgroups = [item for item in (subgroups or []) if item is not None]

    if not subgroups:
        return groups

    missing_group = [item.subgrupo for item in subgroups if getattr(item, "grupo_id", None) is None]
    if missing_group:
        raise serializers.ValidationError(
            {subgroup_field_name: "Todos os subgrupos selecionados precisam estar vinculados a um grupo."}
        )

    parent_groups = {item.grupo for item in subgroups if getattr(item, "grupo", None) is not None}
    if not groups:
        return list(parent_groups)

    group_ids = {item.id for item in groups}
    invalid = [item.subgrupo for item in subgroups if item.grupo_id not in group_ids]
    if invalid:
        raise serializers.ValidationError(
            {subgroup_field_name: "Existem subgrupos que nao pertencem aos grupos selecionados."}
        )

    merged_groups = {item.id: item for item in groups}
    for parent_group in parent_groups:
        merged_groups[parent_group.id] = parent_group
    return list(merged_groups.values())
