from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mercado", "0005_marketnewspost_inline_attachment_ids"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="marketnewspost",
            index=models.Index(
                fields=["-data_publicacao", "-created_at"],
                name="mercado_mnp_ordering_idx",
            ),
        ),
    ]
