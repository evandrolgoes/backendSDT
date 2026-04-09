import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agenda", "0002_agendaeventmetadata"),
        ("clients", "0011_remove_counterparty_clients_cou_tenant__06be5d_idx"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientAgendaEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("titulo", models.CharField(max_length=255)),
                ("descricao", models.TextField(blank=True)),
                ("local", models.CharField(blank=True, max_length=255)),
                ("data_inicio", models.DateField()),
                ("data_fim", models.DateField()),
                ("hora_inicio", models.TimeField(blank=True, null=True)),
                ("hora_fim", models.TimeField(blank=True, null=True)),
                ("dia_todo", models.BooleanField(default=False)),
                ("repeticao", models.CharField(blank=True, choices=[("", "Nao repetir"), ("weekly", "Semanal"), ("monthly", "Mensal")], default="", max_length=20)),
                ("repetir_ate", models.DateField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_clientagendaevents", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="clientagendaevents", to="accounts.tenant")),
                ("grupos", models.ManyToManyField(blank=True, related_name="client_agenda_events", to="clients.economicgroup")),
                ("subgrupos", models.ManyToManyField(blank=True, related_name="client_agenda_events", to="clients.subgroup")),
            ],
            options={
                "ordering": ["data_inicio", "hora_inicio", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="clientagendaevent",
            index=models.Index(fields=["tenant", "data_inicio"], name="agenda_clie_tenant__a5a9b7_idx"),
        ),
        migrations.AddIndex(
            model_name="clientagendaevent",
            index=models.Index(fields=["tenant", "data_fim"], name="agenda_clie_tenant__793fb4_idx"),
        ),
        migrations.AddIndex(
            model_name="clientagendaevent",
            index=models.Index(fields=["tenant", "repeticao"], name="agenda_clie_tenant__f7e77a_idx"),
        ),
    ]
