from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0012_derivativeoperationname"),
    ]

    operations = [
        migrations.RenameField(
            model_name="crop",
            old_name="cultura",
            new_name="ativo",
        ),
        migrations.RenameField(
            model_name="exchange",
            old_name="cultura",
            new_name="ativo",
        ),
    ]
