from django.db import migrations, models
import django.db.models.deletion


def populate_user_types(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.all():
        if getattr(user, "is_superuser", False):
            user.user_type = "admin"
        elif getattr(user, "tenant_id", None):
            user.user_type = "user_admin"
        else:
            user.user_type = "user"
        user.save(update_fields=["user_type"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_relax_tenant_plan_status_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="user_type",
            field=models.CharField(
                choices=[("admin", "Admin"), ("user", "Usuario"), ("user_admin", "Usuario-admin")],
                default="user",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="Invitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("full_name", models.CharField(max_length=150)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("user_type", models.CharField(choices=[("admin", "Admin"), ("user", "Usuario"), ("user_admin", "Usuario-admin")], default="user", max_length=20)),
                ("status", models.CharField(choices=[("pending", "Pendente"), ("sent", "Enviado"), ("accepted", "Aceito"), ("cancelled", "Cancelado")], default="sent", max_length=20)),
                ("message", models.TextField(blank=True)),
                ("expires_at", models.DateField(blank=True, null=True)),
                ("invited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sent_invitations", to="accounts.user")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invitations", to="accounts.tenant")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="invitation",
            index=models.Index(fields=["tenant", "email"], name="accounts_in_tenant__c87443_idx"),
        ),
        migrations.AddIndex(
            model_name="invitation",
            index=models.Index(fields=["tenant", "status"], name="accounts_in_tenant__1112d8_idx"),
        ),
        migrations.RunPython(populate_user_types, migrations.RunPython.noop),
    ]
