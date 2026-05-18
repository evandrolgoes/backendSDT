import re

from rest_framework import serializers

from apps.core.serializers import PrivacyScopedSerializerMixin

from .models import ConfinementDiet, ConfinementLot


class ConfinementDietSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ConfinementDiet
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "created_by"]


class ConfinementLotSerializer(PrivacyScopedSerializerMixin, serializers.ModelSerializer):
    # Derivados expostos como read-only para o dashboard.
    # Modulo 1 (Hedge/Posicao):
    arrobas_previstas = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True,
    )
    arrobas_vendidas = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True,
    )
    arrobas_protegidas = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True,
    )
    arrobas_em_aberto = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True,
    )
    pct_protegido = serializers.DecimalField(
        max_digits=9, decimal_places=4, read_only=True,
    )
    cabecas_em_aberto = serializers.IntegerField(read_only=True)
    # Fase 2 (Margem/crush):
    arrobas_saida_carcaca = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True,
    )
    arrobas_produzidas = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True,
    )

    def _build_next_lot_code(self, tenant):
        queryset = ConfinementLot.objects.all()
        if tenant is not None:
            queryset = queryset.filter(tenant=tenant)

        highest_number = 0
        for code in queryset.values_list("codigo_lote", flat=True):
            match = re.search(r"(\d+)$", str(code or "").strip())
            if match:
                highest_number = max(highest_number, int(match.group(1)))

        return f"LOT-{highest_number + 1:03d}"

    def create(self, validated_data):
        if not str(validated_data.get("codigo_lote") or "").strip():
            validated_data["codigo_lote"] = self._build_next_lot_code(validated_data.get("tenant"))
        return super().create(validated_data)

    class Meta:
        model = ConfinementLot
        fields = "__all__"
        # peso_saida_kg fica gravavel: o model so o sobrepoe quando
        # peso_saida_manual=False (senao respeita o valor informado).
        read_only_fields = [
            "created_at", "updated_at", "created_by",
            "data_saida_projetada",
            "arrobas_previstas", "arrobas_vendidas", "arrobas_protegidas",
            "arrobas_em_aberto", "pct_protegido", "cabecas_em_aberto",
            "arrobas_saida_carcaca", "arrobas_produzidas",
        ]
