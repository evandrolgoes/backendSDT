from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("derivatives", "0005_single_table_derivative_operations"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="derivativeoperation",
            name="volume_financeiro_valor_moeda_brl",
        ),
    ]
