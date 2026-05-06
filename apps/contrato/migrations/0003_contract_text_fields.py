from django.db import migrations, models


def copy_cliente_to_cliente_nome(apps, schema_editor):
    Contract = apps.get_model("contrato", "Contract")
    for contract in Contract.objects.select_related("cliente").all():
        nome = getattr(contract.cliente, "nome", "") if contract.cliente_id else ""
        if nome:
            contract.cliente_nome = nome
            contract.save(update_fields=["cliente_nome"])


class Migration(migrations.Migration):
    dependencies = [
        ("contrato", "0002_alter_contract_cliente"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="cliente_nome",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.RunPython(copy_cliente_to_cliente_nome, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="contract",
            name="cliente",
        ),
        migrations.RenameField(
            model_name="contract",
            old_name="cliente_nome",
            new_name="cliente",
        ),
        migrations.AlterField(
            model_name="contract",
            name="cliente",
            field=models.CharField(max_length=255),
        ),
        migrations.AddField(
            model_name="contract",
            name="cpf_cnpj",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="contract",
            name="endereco",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="contract",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="contract",
            name="telefone",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
    ]
