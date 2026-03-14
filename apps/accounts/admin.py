from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Role, Tenant, User, UserRole


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    search_fields = ("name", "slug")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "full_name", "tenant", "is_active", "is_staff")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("SDT Position", {"fields": ("tenant", "full_name", "phone")}),
    )


admin.site.register(Role)
admin.site.register(UserRole)
