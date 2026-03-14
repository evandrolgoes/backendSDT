from django.contrib import admin

from .models import Strategy, StrategyTrigger, TriggerEvent

admin.site.register(Strategy)
admin.site.register(StrategyTrigger)
admin.site.register(TriggerEvent)
