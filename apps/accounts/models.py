from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import TimeStampedModel
from .managers import UserManager


class Tenant(TimeStampedModel):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    class AccessStatus(models.TextChoices):
        PENDING = "pending", "Pendente"
        ACTIVE = "active", "Ativo"

    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.SET_NULL, related_name="users")
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    access_status = models.CharField(max_length=20, choices=AccessStatus.choices, default=AccessStatus.ACTIVE)
    assigned_groups = models.ManyToManyField("clients.EconomicGroup", blank=True, related_name="assigned_users")
    assigned_subgroups = models.ManyToManyField("clients.SubGroup", blank=True, related_name="assigned_users")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ["username"]
        indexes = [models.Index(fields=["tenant", "username"])]

    def save(self, *args, **kwargs):
        self.is_active = self.access_status == self.AccessStatus.ACTIVE
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


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
