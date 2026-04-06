from django.contrib import admin

from .models import OtherCashOutflow


@admin.register(OtherCashOutflow)
class OtherCashOutflowAdmin(admin.ModelAdmin):
    list_display = ("descricao", "grupo", "subgrupo", "moeda", "valor", "status", "data_pagamento")
    list_filter = ("status", "moeda", "data_pagamento")
    search_fields = ("descricao", "obs", "grupo__grupo", "subgrupo__subgrupo")
