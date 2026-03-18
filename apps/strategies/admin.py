from django.contrib import admin

from .models import CropBoard, HedgePolicy, Strategy, StrategyTrigger

admin.site.register(Strategy)
admin.site.register(StrategyTrigger)
admin.site.register(HedgePolicy)
admin.site.register(CropBoard)
