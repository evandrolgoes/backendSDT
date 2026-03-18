from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0010_exchange_cultura"),
    ]

    operations = [
        migrations.AddField(
            model_name="exchange",
            name="moeda_bolsa",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="exchange",
            name="volume_padrao_contrato",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="exchange",
            name="unidade_bolsa",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="exchange",
            name="moeda_cmdtye",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="exchange",
            name="fator_conversao_unidade_padrao_cultura",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
    ]
