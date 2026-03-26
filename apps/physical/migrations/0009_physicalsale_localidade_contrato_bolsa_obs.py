from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("physical", "0008_physicalsale_grupo_subgrupo_moeda_unidade"),
    ]

    operations = [
        migrations.AddField(
            model_name="physicalsale",
            name="contrato_bolsa",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="physicalsale",
            name="localidade",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="physicalsale",
            name="obs",
            field=models.TextField(blank=True),
        ),
    ]
