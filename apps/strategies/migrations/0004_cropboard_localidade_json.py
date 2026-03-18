from django.db import migrations, models


def convert_localidade_to_json(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        ALTER TABLE strategies_cropboard
        ALTER COLUMN localidade TYPE jsonb
        USING (
            CASE
                WHEN btrim(COALESCE(localidade, '')) = '' THEN '[]'::jsonb
                ELSE jsonb_build_array(localidade)
            END
        );
        """
    )


def revert_localidade_to_varchar(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        ALTER TABLE strategies_cropboard
        ALTER COLUMN localidade TYPE varchar(120)
        USING (
            CASE
                WHEN jsonb_typeof(localidade) = 'array' AND jsonb_array_length(localidade) > 0
                    THEN localidade->>0
                ELSE ''
            END
        );
        """
    )


class Migration(migrations.Migration):
    dependencies = [
        ("strategies", "0003_cropboard_localidade"),
    ]

    operations = [
        migrations.RunPython(
            convert_localidade_to_json,
            revert_localidade_to_varchar,
        ),
        migrations.AlterField(
            model_name="cropboard",
            name="localidade",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
