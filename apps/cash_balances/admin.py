from django.contrib import admin

from .models import CashBalance


@admin.register(CashBalance)
class CashBalanceAdmin(admin.ModelAdmin):
    list_display = ("conta", "banco", "saldo", "moeda", "considerar_no_fluxo", "grupo", "subgrupo")
    list_filter = ("considerar_no_fluxo", "moeda", "banco")
    search_fields = ("conta", "banco", "obs", "grupo__grupo", "subgrupo__subgrupo")
