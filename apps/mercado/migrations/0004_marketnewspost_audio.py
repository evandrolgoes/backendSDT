from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("mercado", "0003_simplify_market_news_editor"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketnewspost",
            name="audio",
            field=models.FileField(blank=True, null=True, upload_to="market_news/audio/"),
        ),
    ]
