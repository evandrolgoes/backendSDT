from rest_framework import serializers

from .models import GamingSession


class GamingSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GamingSession
        fields = [
            "id",
            "game_code",
            "kind",
            "player_name",
            "seed",
            "ts",
            "cost_rsc",
            "area_ha",
            "yield_scha",
            "production_sc",
            "basis_hist",
            "final_price",
            "adj_total",
            "vol_phys",
            "avg_phys",
            "margin",
            "h_m1",
            "h_m2",
            "h_m3",
            "h_m4",
            "h_m5",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
