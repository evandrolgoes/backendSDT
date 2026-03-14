from django.contrib import admin

from .models import BasisSeries, FxRate, MarketPrice

admin.site.register(MarketPrice)
admin.site.register(FxRate)
admin.site.register(BasisSeries)
