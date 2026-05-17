from django.db import migrations


def backfill_precos(apps, schema_editor):
    """Consolida cotações existentes nos novos campos preco_brl / preco_usd.

    - moeda_unidade == "U$/sc" -> preco_usd = cotacao
    - moeda_unidade == "R$/sc" -> preco_brl = cotacao

    Só preenche quando o campo de destino ainda está vazio (idempotente,
    não sobrescreve edição manual).
    """
    PhysicalQuote = apps.get_model("physical", "PhysicalQuote")

    to_update = []
    for quote in PhysicalQuote.objects.all().iterator():
        moeda_unidade = (quote.moeda_unidade or "").strip()
        changed = False
        if moeda_unidade == "U$/sc" and quote.preco_usd is None:
            quote.preco_usd = quote.cotacao
            changed = True
        elif moeda_unidade == "R$/sc" and quote.preco_brl is None:
            quote.preco_brl = quote.cotacao
            changed = True
        if changed:
            to_update.append(quote)

    if to_update:
        PhysicalQuote.objects.bulk_update(to_update, ["preco_brl", "preco_usd"], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("physical", "0021_physicalquote_preco_brl_physicalquote_preco_usd"),
    ]

    operations = [
        migrations.RunPython(backfill_precos, migrations.RunPython.noop),
    ]
