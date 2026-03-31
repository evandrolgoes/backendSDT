from django.db import migrations, models


def delete_internal_user_invitations(apps, schema_editor):
    Invitation = apps.get_model("accounts", "Invitation")
    Invitation.objects.filter(kind="internal_user").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0025_userdatascope"),
    ]

    operations = [
        migrations.RunPython(delete_internal_user_invitations, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="invitation",
            name="kind",
            field=models.CharField(
                choices=[
                    ("farm_owner", "Owner da fazenda"),
                    ("distributor", "Distribuidor"),
                    ("platform_admin", "Usuario admin"),
                ],
                default="platform_admin",
                max_length=30,
            ),
        ),
    ]
