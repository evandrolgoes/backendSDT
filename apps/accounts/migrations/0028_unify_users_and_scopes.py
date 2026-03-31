from django.db import migrations, models


def migrate_user_scopes_to_user_fields(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UserDataScope = apps.get_model("accounts", "UserDataScope")

    for user in User.objects.all():
        scopes = UserDataScope.objects.filter(user=user)
        group_ids = list(scopes.filter(scope_type="group", group__isnull=False).values_list("group_id", flat=True))
        subgroup_ids = list(scopes.filter(scope_type="subgroup", subgroup__isnull=False).values_list("subgroup_id", flat=True))
        access_level = scopes.values_list("access_level", flat=True).first() or "read"

        if hasattr(user, "scope_access_level"):
            User.objects.filter(pk=user.pk).update(scope_access_level=access_level)

        if group_ids:
            user.assigned_groups.set(group_ids)
        if subgroup_ids:
            user.assigned_subgroups.set(subgroup_ids)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0027_invitation_user_fields_and_limits"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="scope_access_level",
            field=models.CharField(
                choices=[("read", "Leitura"), ("write", "Edicao")],
                default="read",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="invitation",
            name="scope_access_level",
            field=models.CharField(
                choices=[("read", "Leitura"), ("write", "Edicao")],
                default="read",
                max_length=20,
            ),
        ),
        migrations.RunPython(migrate_user_scopes_to_user_fields, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="UserDataScope",
        ),
    ]
