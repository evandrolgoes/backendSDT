from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "whatsapp", "landing_page", "perfil", "data")
    search_fields = ("nome", "email", "whatsapp", "empresa_atual", "landing_page")
    list_filter = ("landing_page", "perfil", "data")
