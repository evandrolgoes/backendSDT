from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0008_remove_counterparty_subgrupo"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="counterparty",
            name="clients_cou_tenant__06be5d_idx",
        ),
    ]
