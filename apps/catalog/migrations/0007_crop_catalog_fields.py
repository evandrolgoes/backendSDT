from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_exchange_moeda_unidade_padrao"),
    ]

    operations = [
        migrations.AddField(
            model_name="crop",
            name="bolsa_ref",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="crop",
            name="imagem",
            field=models.ImageField(blank=True, null=True, upload_to="crops/"),
        ),
        migrations.AddField(
            model_name="crop",
            name="moeda_unidade_padrao",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="crop",
            name="unidade_fisico",
            field=models.ManyToManyField(blank=True, related_name="culturas", to="catalog.unit"),
        ),
    ]
