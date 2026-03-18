from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0012_derivativeoperationname"),
        ("derivatives", "0008_alter_derivativeoperation_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="derivativeoperation",
            name="destino_cultura",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="derivativos_destino",
                to="catalog.crop",
            ),
        ),
    ]
