from django.db import migrations, models


def migrate_swap_divida_to_destino_texto(apps, schema_editor):
    DerivativeOperation = apps.get_model("derivatives", "DerivativeOperation")
    DerivativeOperation.objects.filter(swap_divida__iexact="sim").update(
        destino_texto="Swap de pagamento moeda estrangeira"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("derivatives", "0013_derivativeoperation_swap_divida"),
    ]

    operations = [
        migrations.AddField(
            model_name="derivativeoperation",
            name="destino_texto",
            field=models.CharField(max_length=100, blank=True, verbose_name="Destino da operacao (texto)"),
        ),
        migrations.RunPython(migrate_swap_divida_to_destino_texto, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="derivativeoperation",
            name="swap_divida",
        ),
    ]
