import django.db.models.deletion
from django.db import migrations, models


def migrate_cropboard_groups(apps, schema_editor):
    CropBoard = apps.get_model("strategies", "CropBoard")

    for crop_board in CropBoard.objects.all():
        group = crop_board.grupos.order_by("id").first()
        subgroup = crop_board.subgrupos.order_by("id").first()

        crop_board.grupo_id = group.id if group else None
        crop_board.subgrupo_id = subgroup.id if subgroup else None
        crop_board.save(update_fields=["grupo", "subgrupo"])


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0006_economicgroup_owner_economicgroup_users_with_access_and_more'),
        ('strategies', '0004_cropboard_localidade_json'),
    ]

    operations = [
        migrations.AddField(
            model_name='cropboard',
            name='grupo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quadros_safra', to='clients.economicgroup'),
        ),
        migrations.AddField(
            model_name='cropboard',
            name='subgrupo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quadros_safra', to='clients.subgroup'),
        ),
        migrations.RunPython(migrate_cropboard_groups, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='cropboard',
            name='grupos',
        ),
        migrations.RemoveField(
            model_name='cropboard',
            name='subgrupos',
        ),
    ]
