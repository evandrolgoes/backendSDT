from django.contrib import admin

from .models import OtherEntry


@admin.register(OtherEntry)
class OtherEntryAdmin(admin.ModelAdmin):
    list_display = ("descricao", "grupo", "subgrupo", "moeda", "valor", "status", "data_entrada")
    list_filter = ("status", "moeda", "data_entrada")
    search_fields = ("descricao", "obs", "grupo__grupo", "subgrupo__subgrupo")
