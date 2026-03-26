from django.db import migrations, models
import django.db.models.deletion


def migrate_physicalsale_groups(apps, schema_editor):
    PhysicalSale = apps.get_model("physical", "PhysicalSale")

    for sale in PhysicalSale.objects.all():
        group = sale.grupos.order_by("id").first()
        subgroup = sale.subgrupos.order_by("id").first()

        sale.grupo_id = group.id if group else None
        sale.subgrupo_id = subgroup.id if subgroup else None

        if not sale.moeda_unidade:
            moeda_contrato = (sale.moeda_contrato or "").strip()
            unidade_contrato = (sale.unidade_contrato or "").strip()
            if moeda_contrato and unidade_contrato:
                sale.moeda_unidade = f"{moeda_contrato}/{unidade_contrato}"
            elif moeda_contrato:
                sale.moeda_unidade = moeda_contrato

        sale.save(update_fields=["grupo", "subgrupo", "moeda_unidade"])


class Migration(migrations.Migration):

    dependencies = [
        ("physical", "0007_cashpayment_fazer_frente_com_safra"),
    ]

    operations = [
        migrations.AddField(
            model_name="physicalsale",
            name="grupo",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vendas_fisico", to="clients.economicgroup"),
        ),
        migrations.AddField(
            model_name="physicalsale",
            name="moeda_unidade",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="physicalsale",
            name="subgrupo",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vendas_fisico", to="clients.subgroup"),
        ),
        migrations.RunPython(migrate_physicalsale_groups, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="physicalsale",
            name="grupos",
        ),
        migrations.RemoveField(
            model_name="physicalsale",
            name="subgrupos",
        ),
    ]
