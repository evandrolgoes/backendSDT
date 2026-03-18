from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("strategies", "0002_cropboard_hedgepolicy_remove_triggerevent_trigger_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cropboard",
            name="localidade",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
