from django.db import migrations, models

import apps.accounts.constants


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_user_access_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="enabled_modules",
            field=models.JSONField(blank=True, default=apps.accounts.constants.default_enabled_modules),
        ),
        migrations.AddField(
            model_name="tenant",
            name="expires_at",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="max_groups",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="max_subgroups",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="max_users",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="plan_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="tenant",
            name="subscription_status",
            field=models.CharField(blank=True, default="active", max_length=30),
        ),
        migrations.AddField(
            model_name="user",
            name="allowed_modules",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
