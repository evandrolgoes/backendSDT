from django.db import migrations, models


def migrate_strategy_group_lists(apps, schema_editor):
    Strategy = apps.get_model("strategies", "Strategy")

    for strategy in Strategy.objects.select_related("grupo", "subgrupo").all():
        if strategy.grupo_id:
            strategy.grupos.add(strategy.grupo_id)
        if strategy.subgrupo_id:
            strategy.subgrupos.add(strategy.subgrupo_id)


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0006_economicgroup_owner_economicgroup_users_with_access_and_more"),
        ("strategies", "0006_strategytrigger_bolsa_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="strategy",
            name="grupos",
            field=models.ManyToManyField(blank=True, related_name="estrategias_lista", to="clients.economicgroup"),
        ),
        migrations.AddField(
            model_name="strategy",
            name="subgrupos",
            field=models.ManyToManyField(blank=True, related_name="estrategias_lista", to="clients.subgroup"),
        ),
        migrations.RunPython(migrate_strategy_group_lists, migrations.RunPython.noop),
    ]
