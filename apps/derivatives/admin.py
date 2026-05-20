from django.contrib import admin

from .models import DerivativeOperation


@admin.register(DerivativeOperation)
class DerivativeOperationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cod_operacao_mae",
        "nome_da_operacao",
        "ordem",
        "ativo",
        "grupo",
        "subgrupo",
        "contraparte",
        "safra",
        "posicao",
        "tipo_derivativo",
        "contrato_derivativo",
        "bolsa_ref",
        "moeda_ou_cmdtye",
        "numero_lotes",
        "strike_montagem",
        "strike_liquidacao",
        "strike_moeda_unidade",
        "volume_fisico_valor",
        "volume_fisico_unidade",
        "volume_financeiro_valor",
        "volume_financeiro_moeda",
        "data_contratacao",
        "data_liquidacao",
        "status_operacao",
        "ajustes_totais_brl",
        "ajustes_totais_usd",
        "custo_total_montagem_brl",
        "dolar_ptax_vencimento",
        "destino_cultura",
        "destino_texto",
        "tenant",
        "created_by",
        "created_at",
        "updated_at",
    )
    list_display_links = ("id", "cod_operacao_mae")
    list_select_related = (
        "ativo",
        "grupo",
        "subgrupo",
        "contraparte",
        "safra",
        "destino_cultura",
        "tenant",
        "created_by",
    )
    list_filter = (
        "status_operacao",
        "posicao",
        "tipo_derivativo",
        "safra",
        "data_contratacao",
        "tenant",
    )
    search_fields = (
        "cod_operacao_mae",
        "nome_da_operacao",
        "contrato_derivativo",
        "bolsa_ref",
    )
    date_hierarchy = "data_contratacao"
    list_per_page = 50
    ordering = ("cod_operacao_mae", "ordem", "id")
