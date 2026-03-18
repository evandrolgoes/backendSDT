from django.contrib import admin

from .models import Crop, MarketInstrument, PriceSource

admin.site.register(Crop)
admin.site.register(MarketInstrument)
admin.site.register(PriceSource)
