from django.db import migrations


def recreate_assigned_subgroups_tables(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Invitation = apps.get_model("accounts", "Invitation")

    through_models = [
        User._meta.get_field("assigned_subgroups").remote_field.through,
        Invitation._meta.get_field("assigned_subgroups").remote_field.through,
    ]

    existing_tables = set(schema_editor.connection.introspection.table_names())

    for through_model in through_models:
        if through_model._meta.db_table in existing_tables:
            schema_editor.delete_model(through_model)

    for through_model in through_models:
        schema_editor.create_model(through_model)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0028_unify_users_and_scopes"),
    ]

    operations = [
        migrations.RunPython(recreate_assigned_subgroups_tables, migrations.RunPython.noop),
    ]
