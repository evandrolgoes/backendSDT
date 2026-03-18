from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("physical", "0002_actualcost_budgetcost_physicalquote_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="physicalsale",
            name="unidade_contrato",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
