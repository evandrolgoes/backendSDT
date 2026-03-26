from django.contrib import admin

from .models import ReceiptEntry


@admin.register(ReceiptEntry)
class ReceiptEntryAdmin(admin.ModelAdmin):
    list_display = ["cliente", "produto", "status", "valor", "data_recebimento", "data_vencimento"]
    search_fields = ["cliente", "nf", "produto", "status", "observacoes"]
