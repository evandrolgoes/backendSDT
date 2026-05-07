from rest_framework import serializers

from .models import HedgePositionLead, Lead


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id",
            "nome",
            "whatsapp",
            "email",
            "perfil",
            "trabalho_ocupacao_atual",
            "empresa_atual",
            "landing_page",
            "data",
            "objetivo",
            "mensagem",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "data", "created_at", "updated_at"]


class HedgePositionLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = HedgePositionLead
        fields = [
            "id",
            "nome",
            "whatsapp",
            "email",
            "cidade",
            "cultura",
            "area",
            "mensagem",
            "observacao",
            "origem",
            "data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "data", "created_at", "updated_at"]
