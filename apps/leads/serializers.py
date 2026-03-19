from rest_framework import serializers

from .models import Lead


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
