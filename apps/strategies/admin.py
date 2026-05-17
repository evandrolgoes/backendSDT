from django.contrib import admin

from .models import CropBoard, HedgePolicy, Strategy, StrategyTrigger, TriggerAlertLog

admin.site.register(Strategy)
admin.site.register(StrategyTrigger)
admin.site.register(HedgePolicy)
admin.site.register(CropBoard)


@admin.register(TriggerAlertLog)
class TriggerAlertLogAdmin(admin.ModelAdmin):
    list_display = ("contract", "direction", "strike", "price", "email_sent", "sent_at")
    list_filter = ("email_sent", "sent_at")
    search_fields = ("contract", "detail")
    readonly_fields = [f.name for f in TriggerAlertLog._meta.fields]
