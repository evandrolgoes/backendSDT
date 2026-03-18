from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_crop_catalog_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="crop",
            name="moeda_unidade_padrao",
        ),
    ]
