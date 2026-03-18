from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("derivatives", "0006_remove_derivativeoperation_volume_financeiro_valor_moeda_brl"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="derivativeoperation",
            name="liquidacao_ajuste_total_moeda_original",
        ),
    ]
