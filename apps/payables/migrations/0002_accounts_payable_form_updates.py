from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payables", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="accountspayable",
            old_name="referencia",
            new_name="descricao",
        ),
        migrations.AlterField(
            model_name="accountspayable",
            name="descricao",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="accountspayable",
            name="status",
            field=models.CharField(
                choices=[("A pagar", "A pagar"), ("Pago", "Pago")],
                default="A pagar",
                max_length=20,
            ),
        ),
    ]
