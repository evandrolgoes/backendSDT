from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0016_tenant_types_user_roles_admin_invites"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="invitation",
            name="user_type",
        ),
    ]
