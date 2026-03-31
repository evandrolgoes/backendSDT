from collections import Counter

import django.db.models.deletion
from django.db import migrations, models
from apps.auditing.context import suppress_audit_signals


def populate_subgroup_group(apps, schema_editor):
    SubGroup = apps.get_model("clients", "SubGroup")
    EconomicGroup = apps.get_model("clients", "EconomicGroup")

    relation_sources = [
        ("physical", "BudgetCost"),
        ("physical", "ActualCost"),
        ("physical", "PhysicalSale"),
        ("physical", "PhysicalPayment"),
        ("physical", "CashPayment"),
        ("derivatives", "DerivativeOperation"),
        ("strategies", "Strategy"),
        ("strategies", "CropBoard"),
    ]

    subgroup_to_group = {}
    with suppress_audit_signals():
        for app_label, model_name in relation_sources:
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                continue
            field_names = {field.name for field in model._meta.get_fields()}
            if "subgrupo" not in field_names or "grupo" not in field_names:
                continue

            rows = (
                model.objects.exclude(subgrupo_id__isnull=True)
                .exclude(grupo_id__isnull=True)
                .values_list("subgrupo_id", "grupo_id")
            )
            for subgroup_id, group_id in rows:
                counter = subgroup_to_group.setdefault(subgroup_id, Counter())
                counter[group_id] += 1

        for subgroup in SubGroup.objects.all().order_by("tenant_id", "id"):
            selected_group_id = None
            counter = subgroup_to_group.get(subgroup.id)
            if counter:
                selected_group_id = counter.most_common(1)[0][0]
            else:
                tenant_groups = list(EconomicGroup.objects.filter(tenant_id=subgroup.tenant_id).order_by("id").values_list("id", flat=True))
                if len(tenant_groups) == 1:
                    selected_group_id = tenant_groups[0]
                elif tenant_groups:
                    legacy_group, _ = EconomicGroup.objects.get_or_create(
                        tenant_id=subgroup.tenant_id,
                        grupo="Grupo legado",
                    )
                    selected_group_id = legacy_group.id
                else:
                    legacy_group = EconomicGroup.objects.create(
                        tenant_id=subgroup.tenant_id,
                        grupo="Grupo legado",
                    )
                    selected_group_id = legacy_group.id

            SubGroup.objects.filter(pk=subgroup.pk).update(grupo_id=selected_group_id)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0023_alter_invitation_status"),
        ("clients", "0009_remove_counterparty_clients_cou_tenant__06be5d_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="subgroup",
            name="grupo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subgrupos",
                to="clients.economicgroup",
            ),
        ),
        migrations.RunPython(populate_subgroup_group, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="subgroup",
            name="grupo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subgrupos",
                to="clients.economicgroup",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="subgroup",
            name="uq_subgroup_name_tenant",
        ),
        migrations.AddIndex(
            model_name="subgroup",
            index=models.Index(fields=["tenant", "grupo"], name="clients_sub_tenant__5a1a7d_idx"),
        ),
        migrations.AddConstraint(
            model_name="subgroup",
            constraint=models.UniqueConstraint(fields=("tenant", "grupo", "subgrupo"), name="uq_subgroup_name_group"),
        ),
    ]
