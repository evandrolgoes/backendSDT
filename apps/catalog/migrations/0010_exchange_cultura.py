from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0009_crop_bolsa_ref_list"),
    ]

    operations = [
        migrations.AddField(
            model_name="exchange",
            name="cultura",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
