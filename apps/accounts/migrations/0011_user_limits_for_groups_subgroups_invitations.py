from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_user_master_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="max_groups",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="max_invitations",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="max_subgroups",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
