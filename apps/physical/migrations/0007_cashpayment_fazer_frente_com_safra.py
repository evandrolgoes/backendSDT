from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        ("clients", "0003_remove_cropseason_uq_safra_tenant_grupo_and_more"),
        ("physical", "0006_physicalpayment_safra"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashpayment",
            name="fazer_frente_com",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pgtos_caixa", to="catalog.crop"),
        ),
        migrations.AddField(
            model_name="cashpayment",
            name="safra",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pgtos_caixa", to="clients.cropseason"),
        ),
    ]
