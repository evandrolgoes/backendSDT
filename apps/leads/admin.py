from django.contrib import admin

from .models import HedgePositionLead, Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "whatsapp", "landing_page", "perfil", "data")
    search_fields = ("nome", "email", "whatsapp", "empresa_atual", "landing_page")
    list_filter = ("landing_page", "perfil", "data")


@admin.register(HedgePositionLead)
class HedgePositionLeadAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "whatsapp", "cidade", "cultura", "area", "data")
    search_fields = ("nome", "email", "whatsapp", "cidade", "cultura")
    list_filter = ("cultura", "area", "data")
    readonly_fields = ("data", "created_at", "updated_at")
