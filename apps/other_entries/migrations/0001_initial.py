from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0031_user_cep_user_cidade_user_cpf_user_endereco_completo_and_more"),
        ("clients", "0010_restore_subgroup_group_hierarchy"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OtherEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("descricao", models.CharField(max_length=255)),
                ("data_vencimento", models.DateField(blank=True, null=True)),
                ("data_entrada", models.DateField(blank=True, null=True)),
                ("valor", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ("moeda", models.CharField(blank=True, default="R$", max_length=20)),
                ("status", models.CharField(choices=[("Recebido", "Recebido"), ("Previsto", "Previsto")], default="Previsto", max_length=20)),
                ("obs", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_otherentrys", to=settings.AUTH_USER_MODEL)),
                ("grupo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="outras_entradas", to="clients.economicgroup")),
                ("subgrupo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="outras_entradas", to="clients.subgroup")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="otherentrys", to="accounts.tenant")),
            ],
            options={
                "verbose_name": "Outra entrada",
                "verbose_name_plural": "Outras entradas",
                "ordering": ["-data_entrada", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="otherentry",
            index=models.Index(fields=["tenant", "data_entrada"], name="other_entri_tenant__2bcaa6_idx"),
        ),
        migrations.AddIndex(
            model_name="otherentry",
            index=models.Index(fields=["tenant", "data_vencimento"], name="other_entri_tenant__7df5c6_idx"),
        ),
        migrations.AddIndex(
            model_name="otherentry",
            index=models.Index(fields=["tenant", "moeda"], name="other_entri_tenant__f08758_idx"),
        ),
        migrations.AddIndex(
            model_name="otherentry",
            index=models.Index(fields=["tenant", "status"], name="other_entri_tenant__6ec0f9_idx"),
        ),
    ]

