from django.db import migrations, models
import django.db.models.deletion


def migrate_existing_derivatives(apps, schema_editor):
    DerivativeOperation = apps.get_model("derivatives", "DerivativeOperation")
    DerivativeEntry = apps.get_model("derivatives", "DerivativeEntry")

    for operation in DerivativeOperation.objects.all():
        DerivativeEntry.objects.create(
            operacao=operation,
            contrato_derivativo=getattr(operation, "contrato_derivativo", "") or "",
            grupo_montagem=getattr(operation, "compra_venda", "") or "",
            tipo_derivativo=getattr(operation, "tipo_derivativo", "") or "",
            volume=getattr(operation, "volume_fisico", None),
            unidade=getattr(operation, "unidade", "") or "",
            custo_total_montagem_brl=getattr(operation, "custo_total_montagem", None),
            ajustes_totais_brl=getattr(operation, "liquidacao_ajuste_total_brl", None),
            ajustes_totais_usd=getattr(operation, "liquidacao_ajuste_total_moeda_original", None),
            ordem=1,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0012_derivativeoperationname"),
        ("derivatives", "0002_remove_cashsettlement_derivative_operation_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="derivativeoperation",
            name="bolsa_ref",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="derivativeoperation",
            name="status_operacao",
            field=models.CharField(blank=True, default="Em aberto", max_length=30),
        ),
        migrations.RenameField(
            model_name="derivativeoperation",
            old_name="liquidacao_dolar_ptax",
            new_name="dolar_ptax_vencimento",
        ),
        migrations.CreateModel(
            name="DerivativeEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("contrato_derivativo", models.CharField(blank=True, max_length=120)),
                ("grupo_montagem", models.CharField(blank=True, max_length=20)),
                ("tipo_derivativo", models.CharField(blank=True, max_length=30)),
                ("numero_lotes", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("volume", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("unidade", models.CharField(blank=True, max_length=20)),
                ("strike_montagem", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("custo_total_montagem_brl", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ("strike_liquidacao", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("ajustes_totais_brl", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ("ajustes_totais_usd", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ("ordem", models.PositiveIntegerField(default=1)),
                ("operacao", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="itens", to="derivatives.derivativeoperation")),
            ],
            options={"ordering": ["ordem", "id"]},
        ),
        migrations.RunPython(migrate_existing_derivatives, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="derivativeoperation",
            name="compra_venda",
        ),
        migrations.RemoveField(
            model_name="derivativeoperation",
            name="contrato_derivativo",
        ),
        migrations.RemoveField(
            model_name="derivativeoperation",
            name="custo_total_montagem",
        ),
        migrations.RemoveField(
            model_name="derivativeoperation",
            name="liquidacao_ajuste_total_brl",
        ),
        migrations.RemoveField(
            model_name="derivativeoperation",
            name="tipo_derivativo",
        ),
        migrations.RemoveField(
            model_name="derivativeoperation",
            name="unidade",
        ),
        migrations.RemoveField(
            model_name="derivativeoperation",
            name="volume_fisico_unidade_padrao_cultura",
        ),
    ]
