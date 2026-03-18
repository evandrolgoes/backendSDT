from django.contrib import admin

from .models import ActualCost, BudgetCost, PhysicalQuote, PhysicalSale

admin.site.register(PhysicalQuote)
admin.site.register(BudgetCost)
admin.site.register(ActualCost)
admin.site.register(PhysicalSale)
