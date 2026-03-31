from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("mercado", "0004_marketnewspost_audio"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketnewspost",
            name="inline_attachment_ids",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
