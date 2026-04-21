from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0014_alter_crop_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="exchange",
            name="tv_symbol_fmt",
            field=models.CharField(
                blank=True,
                max_length=80,
                help_text="Formato do símbolo TradingView. Ex: BMF:DOL{month}{year}",
            ),
        ),
        migrations.AddField(
            model_name="exchange",
            name="tv_ticker_fmt",
            field=models.CharField(
                blank=True,
                max_length=60,
                help_text="Formato do ticker (sem provider). Ex: DOL{month}{year}",
            ),
        ),
        migrations.AddField(
            model_name="exchange",
            name="tv_months",
            field=models.CharField(
                blank=True,
                max_length=60,
                help_text="Meses de vencimento separados por vírgula. Ex: 1,2,3,4,5,6,7,8,9,10,11,12",
            ),
        ),
        migrations.AddField(
            model_name="exchange",
            name="tv_n_contracts",
            field=models.PositiveSmallIntegerField(
                null=True,
                blank=True,
                help_text="Quantos vencimentos futuros manter simultaneamente.",
            ),
        ),
    ]
