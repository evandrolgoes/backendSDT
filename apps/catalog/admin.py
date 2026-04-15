from django.contrib import admin

from .models import Crop, Exchange, MarketInstrument, PriceSource

admin.site.register(Crop)
admin.site.register(MarketInstrument)
admin.site.register(PriceSource)


@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "volume_padrao_contrato", "unidade_bolsa", "moeda_bolsa", "moeda_cmdtye", "moeda_unidade_padrao", "fator_conversao_unidade_padrao_cultura")
    list_editable = ("volume_padrao_contrato", "unidade_bolsa", "moeda_bolsa")
    search_fields = ("nome", "ativo")
    ordering = ("nome",)
