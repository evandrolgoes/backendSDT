from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from django.contrib.admin.widgets import FilteredSelectMultiple

from apps.clients.models import EconomicGroup, SubGroup
from .constants import AVAILABLE_MODULE_CHOICES, AVAILABLE_MODULE_CODES
from .models import Invitation, Tenant, User


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


class UserAdminForm(forms.ModelForm):
    economic_groups = forms.ModelMultipleChoiceField(
        queryset=EconomicGroup.objects.select_related("tenant").order_by("grupo"),
        required=False,
        label="Grupos",
        widget=FilteredSelectMultiple("Grupos", is_stacked=False),
        help_text="Selecione os grupos cadastrados em Economic Groups.",
    )
    subgroups = forms.ModelMultipleChoiceField(
        queryset=SubGroup.objects.select_related("tenant", "grupo").order_by("subgrupo"),
        required=False,
        label="Subgrupos",
        widget=FilteredSelectMultiple("Subgrupos", is_stacked=False),
        help_text="Selecione os subgrupos cadastrados em Sub Groups.",
    )

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["economic_groups"].initial = self.instance.accessible_groups.all()
            self.fields["subgroups"].initial = self.instance.accessible_subgroups.all()

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            user.accessible_groups.set(self.cleaned_data.get("economic_groups", []))
            user.accessible_subgroups.set(self.cleaned_data.get("subgroups", []))
        return user


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    form = TenantAdminForm
    list_display = (
        "name",
        "slug",
        "requires_master_user",
        "can_send_invitations",
        "can_register_groups",
        "can_register_subgroups",
        "created_at",
    )
    search_fields = ("name", "slug")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Identificacao",
            {
                "fields": (
                    "name",
                    "slug",
                    "requires_master_user",
                    "can_send_invitations",
                    "can_register_groups",
                    "can_register_subgroups",
                )
            },
        ),
        ("Modulos", {"fields": ("enabled_modules",)}),
        ("Sistema", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserAdminForm
    list_display = (
        "username",
        "email",
        "full_name",
        "tenant",
        "role",
        "master_user",
        "max_admin_invitations",
        "max_owned_groups",
        "max_owned_subgroups",
        "access_status",
        "is_active",
    )
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Informacoes pessoais",
            {"fields": ("first_name", "last_name", "full_name", "email", "phone", "cpf", "cep", "estado", "cidade", "endereco_completo")},
        ),
        (
            "Hedge Position",
            {
                "fields": (
                    "tenant",
                    "role",
                    "master_user",
                    "economic_groups",
                    "subgroups",
                    "max_admin_invitations",
                    "max_owned_groups",
                    "max_owned_subgroups",
                    "access_status",
                )
            },
        ),
        ("Permissoes", {"fields": ("is_active", "is_superuser")}),
        ("Datas importantes", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "full_name",
                    "cpf",
                    "cep",
                    "estado",
                    "cidade",
                    "endereco_completo",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    filter_horizontal = ()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if form.instance.pk:
            form.instance.accessible_groups.set(form.cleaned_data.get("economic_groups", []))
            form.instance.accessible_subgroups.set(form.cleaned_data.get("subgroups", []))


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "kind", "tenant", "target_tenant_name", "status", "invited_by", "created_at")
    search_fields = ("full_name", "email", "tenant__name", "target_tenant_name", "target_tenant_slug")
    list_filter = ("kind", "status", "tenant")


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass
