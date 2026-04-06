from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0031_user_cep_user_cidade_user_cpf_user_endereco_completo_and_more"),
        ("clients", "0010_restore_subgroup_group_hierarchy"),
    ]

    operations = [
        migrations.CreateModel(
            name="OtherCashOutflow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("descricao", models.CharField(max_length=255)),
                ("valor", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ("moeda", models.CharField(blank=True, default="R$", max_length=20)),
                ("data_pagamento", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("Pendente", "Pendente"), ("Pago", "Pago")], default="Pendente", max_length=20)),
                ("obs", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_%(class)ss", to=settings.AUTH_USER_MODEL)),
                ("grupo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="outras_saidas_caixa", to="clients.economicgroup")),
                ("subgrupo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="outras_saidas_caixa", to="clients.subgroup")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="accounts.tenant")),
            ],
            options={
                "verbose_name": "Outra saída Caixa",
                "verbose_name_plural": "Outras saídas Caixa",
                "ordering": ["-data_pagamento", "-created_at"],
                "indexes": [
                    models.Index(fields=["tenant", "data_pagamento"], name="other_cash__tenant__661d62_idx"),
                    models.Index(fields=["tenant", "moeda"], name="other_cash__tenant__2b34ea_idx"),
                    models.Index(fields=["tenant", "status"], name="other_cash__tenant__792225_idx"),
                ],
            },
        ),
    ]
