from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from .context import get_current_audit_user, is_audit_suppressed
from .models import Attachment, AuditLog
from .services import create_audit_log, serialize_instance_for_log


def _should_skip(instance):
    return is_audit_suppressed() or isinstance(instance, (AuditLog, Attachment))


@receiver(pre_save)
def capture_pre_save_state(sender, instance, **_kwargs):
    if _should_skip(instance):
        return

    previous = {}
    if instance.pk:
        try:
            previous_instance = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            previous_instance = None
        if previous_instance is not None:
            previous = serialize_instance_for_log(previous_instance)
    instance._audit_before_state = previous


@receiver(post_save)
def create_save_audit_log(sender, instance, created, **_kwargs):
    if _should_skip(instance):
        return

    before = getattr(instance, "_audit_before_state", {})
    after = serialize_instance_for_log(instance)
    create_audit_log("criado" if created else "alterado", instance, before=before, after=after, user=get_current_audit_user())
    if hasattr(instance, "_audit_before_state"):
        delattr(instance, "_audit_before_state")


@receiver(pre_delete)
def capture_pre_delete_state(sender, instance, **_kwargs):
    if _should_skip(instance):
        return
    instance._audit_delete_state = serialize_instance_for_log(instance)


@receiver(post_delete)
def create_delete_audit_log(sender, instance, **_kwargs):
    if _should_skip(instance):
        return

    before = getattr(instance, "_audit_delete_state", {})
    create_audit_log("excluido", instance, before=before, after={}, user=get_current_audit_user())
    if hasattr(instance, "_audit_delete_state"):
        delattr(instance, "_audit_delete_state")
