from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0011_exchange_contract_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="DerivativeOperationName",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=120, unique=True)),
            ],
            options={"ordering": ["nome"]},
        ),
    ]
