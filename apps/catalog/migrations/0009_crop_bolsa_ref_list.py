from django.db import migrations, models


def convert_bolsa_ref_to_json(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        ALTER TABLE catalog_crop
        ALTER COLUMN bolsa_ref TYPE jsonb
        USING (
            CASE
                WHEN btrim(COALESCE(bolsa_ref, '')) = '' THEN '[]'::jsonb
                ELSE jsonb_build_array(bolsa_ref)
            END
        );
        """
    )


def revert_bolsa_ref_to_varchar(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        ALTER TABLE catalog_crop
        ALTER COLUMN bolsa_ref TYPE varchar(60)
        USING (
            CASE
                WHEN jsonb_typeof(bolsa_ref) = 'array' AND jsonb_array_length(bolsa_ref) > 0
                    THEN bolsa_ref->>0
                ELSE ''
            END
        );
        """
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0008_remove_crop_moeda_unidade_padrao"),
    ]

    operations = [
        migrations.RunPython(
            convert_bolsa_ref_to_json,
            revert_bolsa_ref_to_varchar,
        ),
        migrations.AlterField(
            model_name="crop",
            name="bolsa_ref",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
