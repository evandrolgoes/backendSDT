from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0026_remove_internal_user_invitations"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitation",
            name="access_status",
            field=models.CharField(
                choices=[("pending", "Pendente"), ("active", "Ativo")],
                default="active",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="invitation",
            name="master_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="managed_invitations",
                to="accounts.user",
            ),
        ),
        migrations.AddField(
            model_name="invitation",
            name="max_admin_invitations",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="invitation",
            name="username",
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
