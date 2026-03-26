from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0023_alter_invitation_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountsPayable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("data_pagamento", models.DateField(blank=True, null=True)),
                ("data_vencimento", models.DateField(blank=True, null=True)),
                ("empresa", models.CharField(max_length=150)),
                ("forma_pagamento", models.CharField(blank=True, max_length=100)),
                ("obs", models.TextField(blank=True)),
                ("referencia", models.CharField(blank=True, max_length=150)),
                ("status", models.CharField(blank=True, max_length=100)),
                ("valor_total", models.DecimalField(decimal_places=2, max_digits=18)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_%(class)ss",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(class)ss",
                        to="accounts.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Conta a pagar",
                "verbose_name_plural": "Contas a pagar",
                "ordering": ["data_vencimento", "-created_at"],
            },
        ),
    ]
