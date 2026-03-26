from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("physical", "0007_cashpayment_fazer_frente_com_safra"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cashpayment",
            name="volume",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True, verbose_name="Valor parcela"),
        ),
        migrations.AddField(
            model_name="cashpayment",
            name="volume_total_operacao",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True, verbose_name="Volume total da operacao"),
        ),
    ]
