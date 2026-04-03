from datetime import date, datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from .models import Attachment, AuditLog


def normalize_log_value(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bool):
        return value
    return str(value)


def serialize_instance_for_log(instance):
    data = {}

    for field in instance._meta.fields:
        if field.name in {"created_at", "updated_at"}:
            continue
        value = getattr(instance, field.name, None)
        if field.is_relation and value is not None:
            data[field.name] = str(value)
        else:
            data[field.name] = normalize_log_value(value)

    for field in instance._meta.many_to_many:
        data[field.name] = list(getattr(instance, field.name).all().values_list("pk", flat=True)) if instance.pk else []

    return data


def build_log_changes(before, after):
    keys = sorted(set(before.keys()) | set(after.keys()))
    changes = []
    for key in keys:
        previous = before.get(key)
        current = after.get(key)
        if previous != current:
            changes.append({"campo": key, "de": previous, "para": current})
    return changes


def build_log_description(action, formulario, changes):
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


def resolve_audit_tenant(instance, user=None):
    if isinstance(instance, (AuditLog, Attachment)):
        return None
    if instance._meta.label == "accounts.Tenant":
        return instance
    return getattr(instance, "tenant", None) or getattr(user, "tenant", None)


def create_audit_log(action, instance, *, before=None, after=None, user=None):
    if isinstance(instance, (AuditLog, Attachment)):
        return None

    before = before or {}
    after = after or {}
    tenant = resolve_audit_tenant(instance, user=user)
    if tenant is None:
        return None

    formulario = instance._meta.verbose_name.title()
    changes = build_log_changes(before, after)
    return AuditLog.objects.create(
        tenant=tenant,
        user=user if getattr(user, "is_authenticated", False) else None,
        formulario=formulario,
        content_type=ContentType.objects.get_for_model(instance.__class__),
        object_id=instance.pk,
        action=action,
        changes_json={"before": before, "after": after, "changes": changes},
        description=build_log_description(action, formulario, changes),
    )
