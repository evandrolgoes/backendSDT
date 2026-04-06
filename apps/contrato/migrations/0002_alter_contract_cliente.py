from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("contrato", "0001_initial"),
        ("receivables", "0002_alter_receiptentry_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contract",
            name="cliente",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contratos",
                to="receivables.entryclient",
            ),
        ),
    ]
