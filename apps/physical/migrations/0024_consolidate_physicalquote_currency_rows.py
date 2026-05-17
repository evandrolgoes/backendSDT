from collections import defaultdict

from django.db import migrations

from apps.auditing.context import suppress_audit_signals


def consolidate_currency_rows(apps, schema_editor):
    """Consolida linhas de cotação que são a mesma coisa em moedas diferentes.

    Chave (mesma carteira): cultura_texto + localidade + safra + data_report
    + data_pgto.

    - Par limpo (exatamente 1 linha "R$/sc" + 1 linha "U$/sc"): a linha R$
      sobrevive como base (mantém cotacao/moeda_unidade dela), recebe o
      preco_usd da linha U$, herda o obs da U$ (sem duplicar), e a linha U$
      é apagada.
    - Grupos ambíguos (2+ linhas da mesma moeda, ou moeda fora de R$/U$):
      NÃO são tocados — apenas listados no log para tratamento manual.
    - Grupos de 1 linha: intocados.

    Irreversível (apaga linhas): reverse = no-op.
    """
    PhysicalQuote = apps.get_model("physical", "PhysicalQuote")

    groups = defaultdict(list)
    for quote in PhysicalQuote.objects.all().iterator():
        key = (
            quote.tenant_id,
            (quote.cultura_texto or "").strip(),
            (quote.localidade or "").strip(),
            quote.safra_id,
            quote.data_report,
            quote.data_pgto,
        )
        groups[key].append(quote)

    merged = 0
    deleted = 0
    ambiguous = []

    # suppress_audit_signals: o post_save/post_delete de auditoria quebra no
    # contexto de migration (espera o model real, não o histórico).
    with suppress_audit_signals():
        for key, rows in groups.items():
            if len(rows) == 1:
                continue

            brl = [r for r in rows if (r.moeda_unidade or "").strip() == "R$/sc"]
            usd = [r for r in rows if (r.moeda_unidade or "").strip() == "U$/sc"]
            other = [r for r in rows if (r.moeda_unidade or "").strip() not in ("R$/sc", "U$/sc")]

            if len(brl) == 1 and len(usd) == 1 and not other:
                base = brl[0]
                partner = usd[0]

                base.preco_usd = partner.preco_usd if partner.preco_usd is not None else partner.cotacao
                if base.preco_brl is None:
                    base.preco_brl = base.cotacao

                obs_parts = []
                for part in [(base.obs or "").strip(), (partner.obs or "").strip()]:
                    if part and part not in obs_parts:
                        obs_parts.append(part)
                base.obs = " | ".join(obs_parts)

                base.save(update_fields=["preco_usd", "preco_brl", "obs"])
                partner.delete()
                merged += 1
                deleted += 1
            else:
                ambiguous.append((key, len(brl), len(usd), len(other)))

    print(
        f"[consolidate_physicalquote] pares mesclados: {merged} | "
        f"linhas U$ apagadas: {deleted} | grupos ambiguos preservados: {len(ambiguous)}"
    )
    for key, n_brl, n_usd, n_other in ambiguous:
        print(f"  AMBIGUO key={key} R$={n_brl} U$={n_usd} outros={n_other}")


class Migration(migrations.Migration):

    dependencies = [
        ("physical", "0023_physicalquote_basis_physicalquote_bolsa_basis"),
    ]

    operations = [
        migrations.RunPython(consolidate_currency_rows, migrations.RunPython.noop),
    ]
