from django.contrib import admin

from .models import CashSettlement, DerivativeLeg, DerivativeOperation, MarkToMarketSnapshot

admin.site.register(DerivativeOperation)
admin.site.register(DerivativeLeg)
admin.site.register(MarkToMarketSnapshot)
admin.site.register(CashSettlement)
