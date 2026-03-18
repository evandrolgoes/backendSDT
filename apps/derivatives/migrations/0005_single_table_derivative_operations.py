from django.db import migrations, models


def migrate_entries_to_operations(apps, schema_editor):
    DerivativeOperation = apps.get_model("derivatives", "DerivativeOperation")
    DerivativeEntry = apps.get_model("derivatives", "DerivativeEntry")

    for operation in DerivativeOperation.objects.all().order_by("id"):
        entries = list(DerivativeEntry.objects.filter(operacao_id=operation.id).order_by("ordem", "id"))
        if not entries:
            continue

        first_entry = entries[0]
        operation.grupo_montagem = first_entry.grupo_montagem or ""
        operation.tipo_derivativo = first_entry.tipo_derivativo or ""
        operation.numero_lotes = first_entry.numero_lotes
        operation.volume_fisico = first_entry.volume
        operation.strike_montagem = first_entry.strike_montagem
        operation.custo_total_montagem_brl = first_entry.custo_total_montagem_brl
        operation.strike_liquidacao = first_entry.strike_liquidacao
        operation.ajustes_totais_brl = first_entry.ajustes_totais_brl
        operation.ajustes_totais_usd = first_entry.ajustes_totais_usd
        operation.ordem = first_entry.ordem or 1
        operation.save(
            update_fields=[
                "grupo_montagem",
                "tipo_derivativo",
                "numero_lotes",
                "volume_fisico",
                "strike_montagem",
                "custo_total_montagem_brl",
                "strike_liquidacao",
                "ajustes_totais_brl",
                "ajustes_totais_usd",
                "ordem",
            ]
        )

        for entry in entries[1:]:
            DerivativeOperation.objects.create(
                tenant=operation.tenant,
                created_by=operation.created_by,
                created_at=operation.created_at,
                updated_at=operation.updated_at,
                subgrupo=operation.subgrupo,
                grupo=operation.grupo,
                cultura=operation.cultura,
                safra=operation.safra,
                cod_operacao_mae=operation.cod_operacao_mae,
                bolsa_ref=operation.bolsa_ref,
                status_operacao=operation.status_operacao,
                contraparte=operation.contraparte,
                data_contratacao=operation.data_contratacao,
                data_liquidacao=operation.data_liquidacao,
                contrato_derivativo=operation.contrato_derivativo,
                liquidacao_ajuste_total_moeda_original=operation.liquidacao_ajuste_total_moeda_original,
                dolar_ptax_vencimento=operation.dolar_ptax_vencimento,
                moeda_ou_cmdtye=operation.moeda_ou_cmdtye,
                moeda_unidade=operation.moeda_unidade,
                nome_da_operacao=operation.nome_da_operacao,
                unidade=operation.unidade,
                grupo_montagem=entry.grupo_montagem or "",
                tipo_derivativo=entry.tipo_derivativo or "",
                numero_lotes=entry.numero_lotes,
                strike_montagem=entry.strike_montagem,
                custo_total_montagem_brl=entry.custo_total_montagem_brl,
                strike_liquidacao=entry.strike_liquidacao,
                ajustes_totais_brl=entry.ajustes_totais_brl,
                ajustes_totais_usd=entry.ajustes_totais_usd,
                ordem=entry.ordem or 1,
                volume_financeiro_moeda=operation.volume_financeiro_moeda,
                volume_financeiro_valor_moeda_original=operation.volume_financeiro_valor_moeda_original,
                volume_financeiro_valor_moeda_brl=operation.volume_financeiro_valor_moeda_brl,
                volume_fisico=entry.volume,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("derivatives", "0004_derivative_operation_parent_contract_unit"),
    ]

    operations = [
        migrations.AddField(
            model_name="derivativeoperation",
            name="ajustes_totais_brl",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="derivativeoperation",
            name="ajustes_totais_usd",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="derivativeoperation",
            name="custo_total_montagem_brl",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="derivativeoperation",
            name="grupo_montagem",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="derivativeoperation",
            name="numero_lotes",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="derivativeoperation",
            name="ordem",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="derivativeoperation",
            name="strike_liquidacao",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="derivativeoperation",
            name="strike_montagem",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="derivativeoperation",
            name="tipo_derivativo",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.RunPython(migrate_entries_to_operations, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="DerivativeEntry",
        ),
    ]
