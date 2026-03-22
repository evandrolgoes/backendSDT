from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone
from django.utils.crypto import get_random_string


def populate_invitation_tokens(apps, schema_editor):
    Invitation = apps.get_model("accounts", "Invitation")
    for invitation in Invitation.objects.all():
        changed = False
        if not invitation.token:
            invitation.token = get_random_string(48)
            changed = True
        if not invitation.expires_at:
            invitation.expires_at = timezone.localdate() + timedelta(days=7)
            changed = True
        if changed:
            invitation.save(update_fields=["token", "expires_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_tenant_description_max_invitations"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitation",
            name="token",
            field=models.CharField(blank=True, default="", max_length=64, unique=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="invitation",
            name="full_name",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.RunPython(populate_invitation_tokens, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="invitation",
            index=models.Index(fields=["token"], name="accounts_in_token_637d78_idx"),
        ),
    ]
