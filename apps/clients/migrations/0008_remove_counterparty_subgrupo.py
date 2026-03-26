from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0007_counterparty_contraparte"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="counterparty",
            name="subgrupo",
        ),
    ]
