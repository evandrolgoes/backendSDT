from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0023_alter_invitation_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="dashboard_filter",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
