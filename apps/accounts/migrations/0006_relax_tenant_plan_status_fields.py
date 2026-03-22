from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_allow_null_module_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tenant",
            name="plan_name",
            field=models.CharField(blank=True, default="", max_length=120, null=True),
        ),
        migrations.AlterField(
            model_name="tenant",
            name="subscription_status",
            field=models.CharField(blank=True, default="active", max_length=30, null=True),
        ),
    ]
