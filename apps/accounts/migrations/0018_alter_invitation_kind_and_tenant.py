from django.db import migrations, models


def migrate_legacy_invitation_kinds(apps, schema_editor):
    Invitation = apps.get_model("accounts", "Invitation")
    Invitation.objects.filter(kind="client_account").update(kind="farm_owner")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0017_remove_invitation_user_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invitation",
            name="kind",
            field=models.CharField(
                choices=[
                    ("internal_user", "Convite interno"),
                    ("farm_owner", "Owner da fazenda"),
                    ("distributor", "Distribuidor"),
                    ("platform_admin", "Usuario admin"),
                ],
                default="internal_user",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="invitation",
            name="tenant",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name="invitations", to="accounts.tenant"),
        ),
        migrations.RunPython(migrate_legacy_invitation_kinds, migrations.RunPython.noop),
    ]
