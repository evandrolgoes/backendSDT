import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agenda", "0001_initial"),
        ("clients", "0011_remove_counterparty_clients_cou_tenant__06be5d_idx"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AgendaEventMetadata",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event_id", models.CharField(max_length=255)),
                ("config", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_metadatas", to="agenda.googlecalendarconfig")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_agendaeventmetadatas", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="agendaeventmetadatas", to="accounts.tenant")),
                ("grupos", models.ManyToManyField(blank=True, related_name="agenda_event_metadatas", to="clients.economicgroup")),
                ("subgrupos", models.ManyToManyField(blank=True, related_name="agenda_event_metadatas", to="clients.subgroup")),
            ],
            options={
                "ordering": ["config__nome", "event_id"],
            },
        ),
        migrations.AddConstraint(
            model_name="agendaeventmetadata",
            constraint=models.UniqueConstraint(fields=("tenant", "config", "event_id"), name="uq_agenda_event_metadata"),
        ),
        migrations.AddIndex(
            model_name="agendaeventmetadata",
            index=models.Index(fields=["tenant", "config", "event_id"], name="agenda_agend_tenant__af8d8f_idx"),
        ),
    ]
