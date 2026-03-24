from django.contrib import admin

from .models import MarketNewsPost


@admin.register(MarketNewsPost)
class MarketNewsPostAdmin(admin.ModelAdmin):
    list_display = ("titulo", "status_artigo", "data_publicacao", "published_by")
    list_filter = ("status_artigo", "tenant")
    search_fields = ("titulo", "conteudo_html")
