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


class HedgePositionLead(TimeStampedModel):
    nome = models.CharField(max_length=150)
    whatsapp = models.CharField(max_length=30)
    email = models.EmailField()
    cidade = models.CharField(max_length=150, blank=True)
    cultura = models.CharField(max_length=80, blank=True)
    area = models.CharField(max_length=80, blank=True)
    mensagem = models.TextField(blank=True)
    observacao = models.CharField(max_length=255, blank=True)
    origem = models.CharField(max_length=150, blank=True)
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lead_hedgeposition"
        ordering = ["-data", "-created_at"]
        verbose_name = "Lead Hedge Position"
        verbose_name_plural = "Leads Hedge Position"

    def __str__(self):
        return f"{self.nome} - {self.email}"
