from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0024_user_dashboard_filter"),
        ("clients", "0010_restore_subgroup_group_hierarchy"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserDataScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("scope_type", models.CharField(choices=[("group", "Grupo"), ("subgroup", "Subgrupo")], max_length=20)),
                ("access_level", models.CharField(choices=[("read", "Leitura"), ("write", "Edicao")], default="read", max_length=20)),
                ("group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="user_scopes", to="clients.economicgroup")),
                ("subgroup", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="user_scopes", to="clients.subgroup")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="data_scopes", to="accounts.user")),
            ],
            options={
                "ordering": ["user_id", "scope_type", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="userdatascope",
            index=models.Index(fields=["user", "scope_type"], name="accounts_us_user_id_54e9cd_idx"),
        ),
        migrations.AddIndex(
            model_name="userdatascope",
            index=models.Index(fields=["group"], name="accounts_us_group_i_9bdc0d_idx"),
        ),
        migrations.AddIndex(
            model_name="userdatascope",
            index=models.Index(fields=["subgroup"], name="accounts_us_subgro_5bbafb_idx"),
        ),
        migrations.AddConstraint(
            model_name="userdatascope",
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(("scope_type", "group"), ("group__isnull", False), ("subgroup__isnull", True)))
                    | (models.Q(("scope_type", "subgroup"), ("group__isnull", True), ("subgroup__isnull", False)))
                ),
                name="accounts_userdatascope_scope_type_matches_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="userdatascope",
            constraint=models.UniqueConstraint(
                condition=models.Q(("group__isnull", False), ("scope_type", "group")),
                fields=("user", "group"),
                name="uq_userdatascope_user_group",
            ),
        ),
        migrations.AddConstraint(
            model_name="userdatascope",
            constraint=models.UniqueConstraint(
                condition=models.Q(("scope_type", "subgroup"), ("subgroup__isnull", False)),
                fields=("user", "subgroup"),
                name="uq_userdatascope_user_subgroup",
            ),
        ),
    ]
