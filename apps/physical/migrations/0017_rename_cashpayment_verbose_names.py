from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("physical", "0016_alter_cashpayment_options_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="cashpayment",
            options={
                "ordering": ["data_pagamento", "data_vencimento", "-created_at"],
                "verbose_name": "Empréstimo",
                "verbose_name_plural": "Empréstimos",
            },
        ),
    ]
