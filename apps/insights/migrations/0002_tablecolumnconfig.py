import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("insights", "0001_initial"),
        ("accounts", "0031_user_cep_user_cidade_user_cpf_user_endereco_completo_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="TableColumnConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("resource", models.CharField(max_length=120)),
                ("ordered_keys", models.JSONField(default=list)),
                ("hidden_keys", models.JSONField(default=list)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="table_column_configs",
                        to="accounts.tenant",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["tenant"], name="insights_tc_tenant__idx"),
                    models.Index(fields=["tenant", "resource"], name="insights_tc_tenant_res_idx"),
                ],
                "unique_together": {("tenant", "resource")},
            },
        ),
    ]
