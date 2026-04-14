from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="GamingSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("game_code", models.CharField(db_index=True, max_length=30)),
                ("kind", models.CharField(choices=[("CONFIG", "CONFIG"), ("RESULT", "RESULT")], max_length=10)),
                ("player_name", models.CharField(blank=True, max_length=200)),
                ("seed", models.BigIntegerField(blank=True, null=True)),
                ("ts", models.BigIntegerField(default=0)),
                ("cost_rsc", models.FloatField(blank=True, null=True)),
                ("area_ha", models.IntegerField(blank=True, null=True)),
                ("yield_scha", models.IntegerField(blank=True, null=True)),
                ("production_sc", models.IntegerField(blank=True, null=True)),
                ("basis_hist", models.FloatField(blank=True, null=True)),
                ("final_price", models.FloatField(blank=True, null=True)),
                ("adj_total", models.FloatField(blank=True, null=True)),
                ("vol_phys", models.IntegerField(blank=True, null=True)),
                ("avg_phys", models.FloatField(blank=True, null=True)),
                ("margin", models.FloatField(blank=True, null=True)),
                ("h_m1", models.FloatField(blank=True, null=True)),
                ("h_m2", models.FloatField(blank=True, null=True)),
                ("h_m3", models.FloatField(blank=True, null=True)),
                ("h_m4", models.FloatField(blank=True, null=True)),
                ("h_m5", models.FloatField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Gaming Session",
                "verbose_name_plural": "Gaming Sessions",
                "ordering": ["-ts", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="gamingsession",
            index=models.Index(fields=["game_code", "kind"], name="gaming_sess_game_co_kind_idx"),
        ),
        migrations.AddIndex(
            model_name="gamingsession",
            index=models.Index(fields=["game_code", "kind", "ts"], name="gaming_sess_game_co_kind_ts_idx"),
        ),
    ]
