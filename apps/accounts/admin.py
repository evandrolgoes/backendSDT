from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Role, Tenant, User, UserRole


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    search_fields = ("name", "slug")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "full_name", "tenant", "access_status", "is_active", "is_staff")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("SDT Position", {"fields": ("tenant", "full_name", "phone", "access_status", "assigned_groups", "assigned_subgroups")}),
    )
    filter_horizontal = ("assigned_groups", "assigned_subgroups", "groups", "user_permissions")


admin.site.register(Role)
admin.site.register(UserRole)
