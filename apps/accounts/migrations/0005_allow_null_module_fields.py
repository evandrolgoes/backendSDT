from django.db import migrations, models

import apps.accounts.constants


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_tenant_subscription_fields_user_allowed_modules"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tenant",
            name="enabled_modules",
            field=models.JSONField(blank=True, default=apps.accounts.constants.default_enabled_modules, null=True),
        ),
        migrations.AlterField(
            model_name="user",
            name="allowed_modules",
            field=models.JSONField(blank=True, default=list, null=True),
        ),
    ]
