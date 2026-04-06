from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payables", "0002_accounts_payable_form_updates"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="accountspayable",
            name="forma_pagamento",
        ),
        migrations.AddField(
            model_name="accountspayable",
            name="conta_origem",
            field=models.CharField(
                blank=True,
                choices=[("itau Person - Evandro", "itau Person - Evandro"), ("Itau - SDT", "Itau - SDT")],
                max_length=150,
            ),
        ),
        migrations.AlterField(
            model_name="accountspayable",
            name="empresa",
            field=models.CharField(
                choices=[("Evandro PF", "Evandro PF"), ("Flavia pF", "Flavia pF"), ("Impere", "Impere"), ("SDT", "SDT")],
                max_length=150,
            ),
        ),
    ]
