from django.contrib import admin

from .models import Crop, MarketInstrument, PriceSource, UnitOfMeasure

admin.site.register(Crop)
admin.site.register(UnitOfMeasure)
admin.site.register(MarketInstrument)
admin.site.register(PriceSource)
