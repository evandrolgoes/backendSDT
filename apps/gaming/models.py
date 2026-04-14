from django.db import models

from apps.core.models import TimeStampedModel


class GamingSession(TimeStampedModel):
    KIND_CHOICES = [
        ("CONFIG", "CONFIG"),
        ("RESULT", "RESULT"),
    ]

    game_code = models.CharField(max_length=30, db_index=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    player_name = models.CharField(max_length=200, blank=True)
    seed = models.BigIntegerField(null=True, blank=True)
    ts = models.BigIntegerField(default=0)  # JS epoch ms for ordering compatibility

    # Config fields (kind=CONFIG)
    cost_rsc = models.FloatField(null=True, blank=True)
    area_ha = models.IntegerField(null=True, blank=True)
    yield_scha = models.IntegerField(null=True, blank=True)
    production_sc = models.IntegerField(null=True, blank=True)
    basis_hist = models.FloatField(null=True, blank=True)

    # Result fields (kind=RESULT)
    final_price = models.FloatField(null=True, blank=True)
    adj_total = models.FloatField(null=True, blank=True)
    vol_phys = models.IntegerField(null=True, blank=True)
    avg_phys = models.FloatField(null=True, blank=True)
    margin = models.FloatField(null=True, blank=True)

    # Hedge percentages per moment
    h_m1 = models.FloatField(null=True, blank=True)
    h_m2 = models.FloatField(null=True, blank=True)
    h_m3 = models.FloatField(null=True, blank=True)
    h_m4 = models.FloatField(null=True, blank=True)
    h_m5 = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-ts", "-created_at"]
        indexes = [
            models.Index(fields=["game_code", "kind"]),
            models.Index(fields=["game_code", "kind", "ts"]),
        ]
        verbose_name = "Gaming Session"
        verbose_name_plural = "Gaming Sessions"

    def __str__(self):
        return f"{self.game_code} | {self.kind} | {self.player_name or '—'}"
