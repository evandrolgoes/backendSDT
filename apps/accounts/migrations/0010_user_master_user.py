from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_invitation_token_and_signup_flow"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="master_user",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="managed_users", to="accounts.user"),
        ),
    ]
