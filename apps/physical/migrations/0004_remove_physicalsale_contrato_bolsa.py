from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("physical", "0003_alter_physicalsale_unidade_contrato"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="physicalsale",
            name="contrato_bolsa",
        ),
    ]
