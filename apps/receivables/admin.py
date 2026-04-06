from django.contrib import admin

from .models import EntryClient, ReceiptEntry


@admin.register(EntryClient)
class EntryClientAdmin(admin.ModelAdmin):
    list_display = ["nome"]
    search_fields = ["nome"]


@admin.register(ReceiptEntry)
class ReceiptEntryAdmin(admin.ModelAdmin):
    list_display = ["cliente", "produto", "status", "valor", "data_recebimento", "data_vencimento"]
    search_fields = ["cliente__nome", "nf", "produto", "status", "observacoes"]
