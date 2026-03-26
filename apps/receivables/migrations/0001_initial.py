from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0023_alter_invitation_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReceiptEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("cliente", models.CharField(max_length=255)),
                ("data_recebimento", models.DateField(blank=True, null=True)),
                ("data_vencimento", models.DateField(blank=True, null=True)),
                ("nf", models.CharField(blank=True, max_length=100)),
                ("observacoes", models.TextField(blank=True)),
                ("produto", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(blank=True, max_length=100)),
                ("valor", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_receiptentrys",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="receiptentrys", to="accounts.tenant"),
                ),
            ],
            options={
                "verbose_name": "Entrada recebimento",
                "verbose_name_plural": "Entradas recebimentos",
                "ordering": ["-data_recebimento", "-created_at"],
            },
        ),
    ]
