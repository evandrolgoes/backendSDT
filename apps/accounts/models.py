from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.core.models import TimeStampedModel
from .constants import AVAILABLE_MODULE_CODES, default_enabled_modules
from .managers import UserManager


def _normalize_module_codes(module_codes):
    if not isinstance(module_codes, (list, tuple)):
        return []
    normalized = []
    for code in module_codes:
        value = str(code or "").strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


class Tenant(TimeStampedModel):
    class AccountType(models.TextChoices):
        SHARED_CLIENT = "shared_client", "Cliente compartilhado"
        DISTRIBUTOR = "distributor", "Distribuidor"

    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    account_type = models.CharField(max_length=30, choices=AccountType.choices, default=AccountType.SHARED_CLIENT)
    parent_distributor = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_tenants",
    )
    requires_master_user = models.BooleanField(default=False)
    can_send_invitations = models.BooleanField(default=True)
    can_register_groups = models.BooleanField(default=True)
    can_register_subgroups = models.BooleanField(default=True)
    enabled_modules = models.JSONField(default=default_enabled_modules, blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.enabled_modules = _normalize_module_codes(self.enabled_modules)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def is_distributor(self):
        return self.account_type == self.AccountType.DISTRIBUTOR

    def has_full_module_access(self):
        return False

    def get_enabled_modules(self):
        configured = _normalize_module_codes(self.enabled_modules)
        return configured

    def has_module(self, module_code):
        return str(module_code or "").strip() in self.get_enabled_modules()


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        STAFF = "staff", "Staff"
        VIEWER = "viewer", "Viewer"

    class AccessStatus(models.TextChoices):
        PENDING = "pending", "Pendente"
        ACTIVE = "active", "Ativo"

    class ScopeAccessLevel(models.TextChoices):
        READ = "read", "Leitura"
        WRITE = "write", "Edicao"

    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.SET_NULL, related_name="users")
    master_user = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="managed_users")
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    cpf = models.CharField(max_length=20, blank=True)
    cep = models.CharField(max_length=20, blank=True)
    estado = models.CharField(max_length=120, blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    endereco_completo = models.TextField(blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
    access_status = models.CharField(max_length=20, choices=AccessStatus.choices, default=AccessStatus.ACTIVE)
    max_admin_invitations = models.PositiveIntegerField(null=True, blank=True)
    max_owned_groups = models.PositiveIntegerField(null=True, blank=True)
    max_owned_subgroups = models.PositiveIntegerField(null=True, blank=True)
    scope_access_level = models.CharField(max_length=20, choices=ScopeAccessLevel.choices, default=ScopeAccessLevel.READ)
    allowed_modules = models.JSONField(default=list, blank=True, null=True)
    dashboard_filter = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ["username"]
        indexes = [models.Index(fields=["tenant", "username"])]

    def save(self, *args, **kwargs):
        if self.allowed_modules is None:
            self.allowed_modules = []
        self.is_active = self.access_status == self.AccessStatus.ACTIVE
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username

    def get_effective_modules(self):
        if self.is_superuser:
            return list(AVAILABLE_MODULE_CODES)
        if self.tenant_id:
            return self.tenant.get_enabled_modules()
        return list(AVAILABLE_MODULE_CODES)

    def has_full_module_access(self):
        return bool(self.is_superuser)

    def has_module_access(self, module_code):
        if self.has_full_module_access():
            return True
        return str(module_code or "").strip() in self.get_effective_modules()

    def is_tenant_admin(self):
        if self.is_superuser:
            return True
        return self.role in {self.Role.OWNER, self.Role.MANAGER}

    def is_distributor_admin(self):
        if self.is_superuser:
            return True
        return bool(self.tenant_id and self.tenant.is_distributor() and self.role in {self.Role.OWNER, self.Role.MANAGER})

    def is_client_admin(self):
        if self.is_superuser:
            return True
        return bool(self.tenant_id and not self.tenant.is_distributor() and self.role in {self.Role.OWNER, self.Role.MANAGER})

    def is_client_owner(self):
        if self.is_superuser:
            return True
        return bool(self.tenant_id and not self.tenant.is_distributor() and self.role == self.Role.OWNER)

    def is_distributor_owner(self):
        if self.is_superuser:
            return True
        return bool(self.tenant_id and self.tenant.is_distributor() and self.role == self.Role.OWNER)

    def has_tenant_slug(self, *slugs):
        if self.is_superuser:
            return True
        return bool(self.tenant_id and self.tenant.slug in set(slugs))

    def get_master_root(self):
        return self.master_user or self

    def get_master_cohort(self):
        root = self.get_master_root()
        return User.objects.filter(models.Q(id=root.id) | models.Q(master_user=root))

    def get_internal_team_cohort(self):
        root = self.get_master_root()
        return User.objects.filter(models.Q(id=root.id) | models.Q(master_user=root)).exclude(tenant__slug="usuario")

    def get_active_admin_invitation_count(self):
        return self.sent_invitations.filter(status=Invitation.Status.PENDING).count()

    def get_owned_groups_count(self):
        return self.owned_groups.count()

    def get_owned_subgroups_count(self):
        return self.owned_subgroups.count()


class Invitation(TimeStampedModel):
    class Kind(models.TextChoices):
        FARM_OWNER = "farm_owner", "Owner da fazenda"
        DISTRIBUTOR = "distributor", "Distribuidor"
        PLATFORM_ADMIN = "platform_admin", "Usuario admin"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        ACCEPTED = "accepted", "Cadastro realizado"
        EXPIRED = "expired", "Expirado"

    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.CASCADE, related_name="invitations")
    kind = models.CharField(max_length=30, choices=Kind.choices, default=Kind.PLATFORM_ADMIN)
    token = models.CharField(max_length=64, unique=True, blank=True)
    target_tenant_name = models.CharField(max_length=150, blank=True)
    target_tenant_slug = models.SlugField(blank=True)
    username = models.CharField(max_length=150, blank=True)
    full_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    access_status = models.CharField(max_length=20, choices=User.AccessStatus.choices, default=User.AccessStatus.ACTIVE)
    max_admin_invitations = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    message = models.TextField(blank=True)
    expires_at = models.DateField(null=True, blank=True)
    scope_access_level = models.CharField(max_length=20, choices=User.ScopeAccessLevel.choices, default=User.ScopeAccessLevel.READ)
    invited_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_invitations")
    master_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="managed_invitations")
    accepted_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="accepted_invitations")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "email"]), models.Index(fields=["tenant", "status"]), models.Index(fields=["token"])]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = get_random_string(48)
        if not self.expires_at:
            self.expires_at = timezone.localdate() + timedelta(days=7)
        super().save(*args, **kwargs)

    def __str__(self):
        display_name = self.full_name or self.email
        return f"{display_name} <{self.email}>"


class Role(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_roles")

    class Meta:
        unique_together = ("user", "role")

    def __str__(self):
        return f"{self.user} - {self.role}"
