from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("agenda", "0003_clientagendaevent"),
    ]

    operations = [
        migrations.DeleteModel(
            name="AgendaEventMetadata",
        ),
    ]
