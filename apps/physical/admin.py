from django.contrib import admin

from .models import ActualCost, BudgetCost, CashPayment, Custo, PhysicalQuote, PhysicalSale

admin.site.register(PhysicalQuote)
admin.site.register(BudgetCost)
admin.site.register(ActualCost)
admin.site.register(PhysicalSale)
admin.site.register(CashPayment)
admin.site.register(Custo)
