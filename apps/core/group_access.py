from rest_framework import serializers


def get_user_assignment_scope(user):
    if not getattr(user, "is_authenticated", False):
        return {
            "has_scope": False,
            "direct_group_ids": [],
            "direct_subgroup_ids": [],
        }

    direct_group_ids = set(user.assigned_groups.values_list("id", flat=True))
    direct_subgroup_ids = set(user.assigned_subgroups.values_list("id", flat=True))

    return {
        "has_scope": bool(direct_group_ids or direct_subgroup_ids),
        "direct_group_ids": list(direct_group_ids),
        "direct_subgroup_ids": list(direct_subgroup_ids),
    }


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
