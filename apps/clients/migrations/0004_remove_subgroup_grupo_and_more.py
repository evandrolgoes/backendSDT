from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0003_remove_cropseason_uq_safra_tenant_grupo_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="subgroup",
            name="uq_subgroup_name_group",
        ),
        migrations.RemoveIndex(
            model_name="subgroup",
            name="clients_sub_tenant__5a1a7d_idx",
        ),
        migrations.RemoveField(
            model_name="subgroup",
            name="grupo",
        ),
        migrations.AddConstraint(
            model_name="subgroup",
            constraint=models.UniqueConstraint(fields=("tenant", "subgrupo"), name="uq_subgroup_name_tenant"),
        ),
        migrations.AddIndex(
            model_name="subgroup",
            index=models.Index(fields=["tenant", "subgrupo"], name="clients_sub_tenant__a95ab3_idx"),
        ),
    ]
