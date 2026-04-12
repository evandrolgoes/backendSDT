from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("strategies", "0007_strategy_grupos_strategy_subgrupos"),
    ]

    operations = [
        migrations.AddField(
            model_name="cropboard",
            name="data_colheita",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cropboard",
            name="data_plantio",
            field=models.DateField(blank=True, null=True),
        ),
    ]
