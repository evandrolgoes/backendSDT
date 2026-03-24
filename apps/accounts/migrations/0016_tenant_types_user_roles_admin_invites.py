from django.db import migrations, models
import django.db.models.deletion


def populate_roles_and_invitation_kinds(apps, schema_editor):
    Tenant = apps.get_model("accounts", "Tenant")
    User = apps.get_model("accounts", "User")
    Invitation = apps.get_model("accounts", "Invitation")

    Tenant.objects.filter(account_type__isnull=True).update(account_type="shared_client")

    for user in User.objects.all():
        if user.is_superuser:
            user.role = "owner"
        elif user.master_user_id:
            user.role = "staff"
        elif user.is_staff:
            user.role = "owner"
        else:
            user.role = "staff"
        user.save(update_fields=["role"])

    Invitation.objects.filter(kind="").update(kind="internal_user")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_remove_user_user_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="account_type",
            field=models.CharField(choices=[("shared_client", "Cliente compartilhado"), ("distributor", "Distribuidor")], default="shared_client", max_length=30),
        ),
        migrations.AddField(
            model_name="tenant",
            name="parent_distributor",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="managed_tenants", to="accounts.tenant"),
        ),
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(choices=[("owner", "Owner"), ("manager", "Manager"), ("staff", "Staff"), ("viewer", "Viewer")], default="staff", max_length=20),
        ),
        migrations.AddField(
            model_name="invitation",
            name="kind",
            field=models.CharField(choices=[("internal_user", "Convite interno"), ("client_account", "Convite de cliente")], default="internal_user", max_length=30),
        ),
        migrations.AddField(
            model_name="invitation",
            name="target_tenant_name",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="invitation",
            name="target_tenant_slug",
            field=models.SlugField(blank=True),
        ),
        migrations.RunPython(populate_roles_and_invitation_kinds, migrations.RunPython.noop),
    ]
