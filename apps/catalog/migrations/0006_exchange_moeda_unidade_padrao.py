from django.db import migrations, models


def seed_exchange_defaults(apps, schema_editor):
    Exchange = apps.get_model("catalog", "Exchange")
    defaults = {
        "B3": "R$/sc",
        "CME": "U$/bus",
    }
    for nome, moeda_unidade_padrao in defaults.items():
        Exchange.objects.filter(nome=nome, moeda_unidade_padrao="").update(moeda_unidade_padrao=moeda_unidade_padrao)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0005_currency_exchange_priceunit_unit"),
    ]

    operations = [
        migrations.AddField(
            model_name="exchange",
            name="moeda_unidade_padrao",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.RunPython(seed_exchange_defaults, migrations.RunPython.noop),
    ]
