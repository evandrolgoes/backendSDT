from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0031_user_cep_user_cidade_user_cpf_user_endereco_completo_and_more"),
        ("receivables", "0002_alter_receiptentry_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Contract",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("frequencia_pagamentos", models.CharField(max_length=120)),
                (
                    "status_contrato",
                    models.CharField(
                        choices=[
                            ("Pendente assinatura", "Pendente assinatura"),
                            ("Pendente formalizacao", "Pendente formalizacao"),
                            ("Assinado", "Assinado"),
                        ],
                        default="Pendente assinatura",
                        max_length=30,
                    ),
                ),
                ("produto", models.CharField(max_length=255)),
                ("valor", models.DecimalField(decimal_places=2, max_digits=18)),
                ("data_inicio_contrato", models.DateField()),
                ("data_fim_contrato", models.DateField()),
                ("valor_total_contrato", models.DecimalField(decimal_places=2, max_digits=18)),
                ("descricao", models.TextField(blank=True)),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contratos",
                        to="receivables.entryclient",
                    ),
                ),
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
                "verbose_name": "Contrato",
                "verbose_name_plural": "Contratos",
                "ordering": ["-data_inicio_contrato", "-created_at"],
            },
        ),
    ]
