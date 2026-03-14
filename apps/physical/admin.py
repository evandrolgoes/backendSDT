from django.contrib import admin

from .models import HedgeAllocation, PhysicalSale

admin.site.register(PhysicalSale)
admin.site.register(HedgeAllocation)
