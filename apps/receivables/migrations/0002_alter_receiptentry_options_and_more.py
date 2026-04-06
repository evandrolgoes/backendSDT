import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_receipt_clients(apps, schema_editor):
    ReceiptEntry = apps.get_model("receivables", "ReceiptEntry")
    EntryClient = apps.get_model("receivables", "EntryClient")

    cached_client_ids = {}

    for entry in ReceiptEntry.objects.all().only("id", "tenant_id", "cliente").iterator():
        client_name = (entry.cliente or "").strip() or "Cliente sem nome"
        cache_key = (entry.tenant_id, client_name.casefold())

        client_id = cached_client_ids.get(cache_key)
        if client_id is None:
            client, _created = EntryClient.objects.get_or_create(
                tenant_id=entry.tenant_id,
                nome=client_name,
            )
            client_id = client.id
            cached_client_ids[cache_key] = client_id

        ReceiptEntry.objects.filter(pk=entry.pk).update(cliente_v2_id=client_id)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0031_user_cep_user_cidade_user_cpf_user_endereco_completo_and_more"),
        ("receivables", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="receiptentry",
            options={"ordering": ["-data_recebimento", "-created_at"], "verbose_name": "Entrada", "verbose_name_plural": "Entradas"},
        ),
        migrations.AlterField(
            model_name="receiptentry",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_%(class)ss", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="receiptentry",
            name="nf",
            field=models.CharField(choices=[("Desnecessario", "Desnecessario"), ("Feito e enviado", "Feito e enviado"), ("Pendente", "Pendente")], default="Desnecessario", max_length=30),
        ),
        migrations.AlterField(
            model_name="receiptentry",
            name="status",
            field=models.CharField(choices=[("Recebido", "Recebido"), ("Previsto", "Previsto")], default="Previsto", max_length=20),
        ),
        migrations.AlterField(
            model_name="receiptentry",
            name="tenant",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="accounts.tenant"),
        ),
        migrations.CreateModel(
            name="EntryClient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("nome", models.CharField(max_length=255)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="accounts.tenant")),
            ],
            options={
                "verbose_name": "Cliente",
                "verbose_name_plural": "Clientes",
                "ordering": ["nome"],
            },
        ),
        migrations.AddConstraint(
            model_name="entryclient",
            constraint=models.UniqueConstraint(fields=("tenant", "nome"), name="uq_entry_client_nome_tenant"),
        ),
        migrations.AddField(
            model_name="receiptentry",
            name="cliente_v2",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="entradas", to="receivables.entryclient"),
        ),
        migrations.RunPython(migrate_receipt_clients, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="receiptentry",
            name="cliente",
        ),
        migrations.RenameField(
            model_name="receiptentry",
            old_name="cliente_v2",
            new_name="cliente",
        ),
        migrations.AlterField(
            model_name="receiptentry",
            name="cliente",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="entradas", to="receivables.entryclient"),
        ),
    ]
