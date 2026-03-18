from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auditing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="alteracoes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="formulario",
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
