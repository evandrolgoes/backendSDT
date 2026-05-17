from django.db import migrations

from apps.auditing.context import suppress_audit_signals


TESTE_SLUG = "teste"


def create_teste_tenant(apps, schema_editor):
    Tenant = apps.get_model("accounts", "Tenant")
    # Espelha o tenant "usuario" (experiencia normal do produtor), porem isolado:
    # is_test=True, sem carteira obrigatoria e sem direito a convidar.
    with suppress_audit_signals():
        Tenant.objects.update_or_create(
            slug=TESTE_SLUG,
            defaults={
                "name": "Teste",
                "is_active": True,
                "is_test": True,
                "account_type": "shared_client",
                "requires_master_user": False,
                "can_send_invitations": False,
                "can_register_groups": True,
                "can_register_subgroups": True,
                "enabled_modules": [],
            },
        )


def remove_teste_tenant(apps, schema_editor):
    Tenant = apps.get_model("accounts", "Tenant")
    User = apps.get_model("accounts", "User")
    tenant = Tenant.objects.filter(slug=TESTE_SLUG).first()
    # So remove se nenhum usuario teste foi criado (reverse seguro).
    if tenant and not User.objects.filter(tenant=tenant).exists():
        with suppress_audit_signals():
            tenant.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0032_invitation_is_test_tenant_is_test"),
    ]

    operations = [
        migrations.RunPython(create_teste_tenant, remove_teste_tenant),
    ]
