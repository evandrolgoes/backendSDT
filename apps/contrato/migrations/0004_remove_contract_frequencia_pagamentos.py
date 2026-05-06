from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("contrato", "0003_contract_text_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="contract",
            name="frequencia_pagamentos",
        ),
    ]
