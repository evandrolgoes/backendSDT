from django.db import models

from apps.core.models import TimeStampedModel


class Lead(TimeStampedModel):
    nome = models.CharField(max_length=150)
    whatsapp = models.CharField(max_length=30)
    email = models.EmailField()
    perfil = models.CharField(max_length=80)
    trabalho_ocupacao_atual = models.CharField(max_length=150)
    empresa_atual = models.CharField(max_length=150)
    landing_page = models.CharField(max_length=150)
    data = models.DateTimeField(auto_now_add=True)
    objetivo = models.CharField(max_length=200)
    mensagem = models.TextField(blank=True)

    class Meta:
        ordering = ["-data", "-created_at"]

    def __str__(self):
        return f"{self.nome} - {self.landing_page}"
