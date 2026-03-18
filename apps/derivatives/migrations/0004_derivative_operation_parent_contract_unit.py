from django.db import migrations, models


def populate_parent_contract_and_unit(apps, schema_editor):
    DerivativeOperation = apps.get_model("derivatives", "DerivativeOperation")

    for operation in DerivativeOperation.objects.prefetch_related("itens").all():
        first_item = operation.itens.order_by("ordem", "id").first()
        if not first_item:
            continue
        changed = False
        if not operation.contrato_derivativo and first_item.contrato_derivativo:
            operation.contrato_derivativo = first_item.contrato_derivativo
            changed = True
        if not operation.unidade and first_item.unidade:
            operation.unidade = first_item.unidade
            changed = True
        if changed:
            operation.save(update_fields=["contrato_derivativo", "unidade"])


class Migration(migrations.Migration):
    dependencies = [
        ("derivatives", "0003_derivative_entry_parent_refactor"),
    ]

    operations = [
        migrations.AddField(
            model_name="derivativeoperation",
            name="contrato_derivativo",
            field=models.CharField(blank=True, default="", max_length=120),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="derivativeoperation",
            name="unidade",
            field=models.CharField(blank=True, default="", max_length=20),
            preserve_default=False,
        ),
        migrations.RunPython(populate_parent_contract_and_unit, migrations.RunPython.noop),
    ]
