from django.contrib import admin

from .models import Broker, ClientAccount, Counterparty, CropSeason, EconomicGroup, SubGroup

admin.site.register(ClientAccount)
admin.site.register(EconomicGroup)
admin.site.register(SubGroup)
admin.site.register(CropSeason)
admin.site.register(Counterparty)
admin.site.register(Broker)
