from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.core.models import TimeStampedModel
from .constants import AVAILABLE_MODULE_CODES, default_enabled_modules
from .managers import UserManager


class Tenant(TimeStampedModel):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    plan_name = models.CharField(max_length=120, blank=True, null=True, default="")
    subscription_status = models.CharField(max_length=30, blank=True, null=True, default="active")
    expires_at = models.DateField(null=True, blank=True)
    max_groups = models.PositiveIntegerField(null=True, blank=True)
    max_subgroups = models.PositiveIntegerField(null=True, blank=True)
    max_users = models.PositiveIntegerField(null=True, blank=True)
    max_invitations = models.PositiveIntegerField(null=True, blank=True)
    enabled_modules = models.JSONField(default=default_enabled_modules, blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.enabled_modules:
            self.enabled_modules = default_enabled_modules()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_enabled_modules(self):
        configured = self.enabled_modules or []
        if not configured:
            return list(AVAILABLE_MODULE_CODES)
        return [code for code in AVAILABLE_MODULE_CODES if code in configured]

    def has_module(self, module_code):
        return module_code in self.get_enabled_modules()


class User(AbstractUser):
    class UserType(models.TextChoices):
        ADMIN = "admin", "Admin"
        USER = "user", "Usuario"
        USER_ADMIN = "user_admin", "Usuario-admin"

    class AccessStatus(models.TextChoices):
        PENDING = "pending", "Pendente"
        ACTIVE = "active", "Ativo"

    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.SET_NULL, related_name="users")
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    user_type = models.CharField(max_length=20, choices=UserType.choices, default=UserType.USER)
    access_status = models.CharField(max_length=20, choices=AccessStatus.choices, default=AccessStatus.ACTIVE)
    assigned_groups = models.ManyToManyField("clients.EconomicGroup", blank=True, related_name="assigned_users")
    assigned_subgroups = models.ManyToManyField("clients.SubGroup", blank=True, related_name="assigned_users")
    allowed_modules = models.JSONField(default=list, blank=True, null=True)
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

    def get_allowed_modules(self):
        if self.is_superuser:
            return list(AVAILABLE_MODULE_CODES)
        configured = self.allowed_modules or []
        return [code for code in AVAILABLE_MODULE_CODES if code in configured]

    def get_effective_modules(self):
        if self.is_superuser:
            return list(AVAILABLE_MODULE_CODES)

        tenant_modules = self.tenant.get_enabled_modules() if self.tenant_id else list(AVAILABLE_MODULE_CODES)
        allowed_modules = self.get_allowed_modules()

        if not allowed_modules:
            return tenant_modules

        return [code for code in tenant_modules if code in allowed_modules]

    def has_module_access(self, module_code):
        if self.is_superuser:
            return True
        return module_code in self.get_effective_modules()

    def is_tenant_admin(self):
        if self.is_superuser:
            return True
        return self.user_type in {self.UserType.ADMIN, self.UserType.USER_ADMIN}


class Invitation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviado"
        ACCEPTED = "accepted", "Aceito"
        CANCELLED = "cancelled", "Cancelado"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="invitations")
    token = models.CharField(max_length=64, unique=True, blank=True)
    full_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    user_type = models.CharField(max_length=20, choices=User.UserType.choices, default=User.UserType.USER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT)
    message = models.TextField(blank=True)
    expires_at = models.DateField(null=True, blank=True)
    invited_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_invitations")

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
