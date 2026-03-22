from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_user_type_invitation"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="description",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="tenant",
            name="max_invitations",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
