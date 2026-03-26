from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("clients", "0007_counterparty_contraparte"),
    ]

    operations = [
        migrations.CreateModel(
            name="Anotacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("titulo", models.CharField(max_length=220)),
                ("data", models.DateField(blank=True, null=True)),
                ("participantes", models.TextField(blank=True)),
                ("conteudo_html", models.TextField(blank=True)),
                (
                    "created_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_%(class)ss", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "modificado_por",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="modified_anotacoes", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "tenant",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="accounts.tenant"),
                ),
            ],
            options={
                "verbose_name": "Anotacao",
                "verbose_name_plural": "Anotacoes",
                "ordering": ["-data", "-updated_at", "-created_at"],
            },
        ),
        migrations.AddField(
            model_name="anotacao",
            name="grupos",
            field=models.ManyToManyField(blank=True, related_name="anotacoes", to="clients.economicgroup"),
        ),
        migrations.AddField(
            model_name="anotacao",
            name="subgrupos",
            field=models.ManyToManyField(blank=True, related_name="anotacoes", to="clients.subgroup"),
        ),
        migrations.AddIndex(
            model_name="anotacao",
            index=models.Index(fields=["tenant", "data"], name="anotacoes_a_tenant__ddd516_idx"),
        ),
        migrations.AddIndex(
            model_name="anotacao",
            index=models.Index(fields=["tenant", "titulo"], name="anotacoes_a_tenant__5607f8_idx"),
        ),
    ]
