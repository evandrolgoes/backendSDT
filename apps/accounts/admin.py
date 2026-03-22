from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .constants import AVAILABLE_MODULE_CHOICES, AVAILABLE_MODULE_CODES
from .models import Invitation, Role, Tenant, User, UserRole


class TenantAdminForm(forms.ModelForm):
    enabled_modules = forms.MultipleChoiceField(
        choices=AVAILABLE_MODULE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Modulos habilitados",
    )

    class Meta:
        model = Tenant
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["enabled_modules"].initial = self.instance.get_enabled_modules() if self.instance.pk else list(AVAILABLE_MODULE_CODES)

    def clean_enabled_modules(self):
        selected = self.cleaned_data.get("enabled_modules") or []
        return list(selected or AVAILABLE_MODULE_CODES)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    form = TenantAdminForm
    list_display = (
        "name",
        "slug",
        "subscription_status",
        "max_groups",
        "max_subgroups",
        "max_users",
        "max_invitations",
        "current_groups",
        "current_subgroups",
        "current_users",
        "current_invitations",
        "created_at",
    )
    search_fields = ("name", "slug")
    readonly_fields = ("current_groups", "current_subgroups", "current_users", "current_invitations", "created_at", "updated_at")
    fieldsets = (
        ("Identificacao", {"fields": ("name", "slug", "description", "subscription_status", "expires_at")}),
        ("Limites contratados", {"fields": ("max_groups", "max_subgroups", "max_users", "max_invitations")}),
        ("Uso atual", {"fields": ("current_groups", "current_subgroups", "current_users", "current_invitations")}),
        ("Modulos", {"fields": ("enabled_modules",)}),
        ("Sistema", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Grupos atuais")
    def current_groups(self, obj):
        return obj.economicgroups.count()

    @admin.display(description="Subgrupos atuais")
    def current_subgroups(self, obj):
        return obj.subgroups.count()

    @admin.display(description="Usuarios atuais")
    def current_users(self, obj):
        return obj.users.filter(is_superuser=False).count()

    @admin.display(description="Convites atuais")
    def current_invitations(self, obj):
        return obj.invitations.filter(status__in=[Invitation.Status.PENDING, Invitation.Status.SENT]).count()


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "full_name", "tenant", "user_type", "access_status", "is_active", "is_staff")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Hedge Position", {"fields": ("tenant", "full_name", "phone", "user_type", "access_status", "assigned_groups", "assigned_subgroups")}),
    )
    filter_horizontal = ("assigned_groups", "assigned_subgroups", "groups", "user_permissions")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "tenant", "user_type", "status", "invited_by", "created_at")
    search_fields = ("full_name", "email", "tenant__name")
    list_filter = ("status", "user_type", "tenant")


admin.site.register(Role)
admin.site.register(UserRole)
