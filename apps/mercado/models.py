from django.conf import settings
from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class MarketNewsPost(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_PUBLISHED, "Publicado"),
    ]

    titulo = models.CharField(max_length=220)
    categorias = models.JSONField(default=list, blank=True)
    status_artigo = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    data_publicacao = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_market_news_posts",
    )
    audio = models.FileField(upload_to="market_news/audio/", null=True, blank=True)
    conteudo_html = models.TextField(blank=True)

    class Meta:
        ordering = ["-data_publicacao", "-created_at"]
        verbose_name = "Market news post"
        verbose_name_plural = "Market news posts"

    def __str__(self):
        return self.titulo
