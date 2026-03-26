from django.conf import settings
from django.db import models

from apps.clients.models import EconomicGroup, SubGroup
from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class Anotacao(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    titulo = models.CharField(max_length=220)
    data = models.DateField(null=True, blank=True)
    grupos = models.ManyToManyField(EconomicGroup, blank=True, related_name="anotacoes")
    subgrupos = models.ManyToManyField(SubGroup, blank=True, related_name="anotacoes")
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="modified_anotacoes",
    )
    participantes = models.TextField(blank=True)
    conteudo_html = models.TextField(blank=True)

    class Meta:
        ordering = ["-data", "-updated_at", "-created_at"]
        verbose_name = "Anotacao"
        verbose_name_plural = "Anotacoes"
        indexes = [
            models.Index(fields=["tenant", "data"]),
            models.Index(fields=["tenant", "titulo"]),
        ]

    def __str__(self):
        return self.titulo

