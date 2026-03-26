from django.conf import settings
from django.db import models

from apps.core.models import TenantAwareModel, TimeStampedModel


class ClientAccount(TenantAwareModel, TimeStampedModel):
    class ProfileType(models.TextChoices):
        PRODUCER = "producer", "Producer"
        COOPERATIVE = "cooperative", "Cooperative"
        TRADER = "trader", "Trader"
        INDUSTRY = "industry", "Industry"

    name = models.CharField(max_length=120)
    legal_name = models.CharField(max_length=180, blank=True)
    document = models.CharField(max_length=30, blank=True)
    profile_type = models.CharField(max_length=20, choices=ProfileType.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["tenant", "document"], name="uq_client_document_tenant")]
        indexes = [models.Index(fields=["tenant", "name"])]

    def __str__(self):
        return self.name


class EconomicGroup(TenantAwareModel):
    grupo = models.CharField(max_length=120, null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_groups",
    )
    users_with_access = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="accessible_groups",
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "grupo"], name="uq_group_name_tenant")]
        indexes = [models.Index(fields=["tenant", "grupo"])]

    def __str__(self):
        return self.grupo


class SubGroup(TenantAwareModel):
    subgrupo = models.CharField(max_length=120, null=True, blank=True)
    descricao = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_subgroups",
    )
    users_with_access = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="accessible_subgroups",
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "subgrupo"], name="uq_subgroup_name_tenant")]
        indexes = [models.Index(fields=["tenant", "subgrupo"])]

    def __str__(self):
        return self.subgrupo


class CropSeason(TenantAwareModel):
    safra = models.CharField(max_length=40, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "safra"], name="uq_safra_tenant")]
        indexes = [models.Index(fields=["tenant", "safra"])]

    def __str__(self):
        return self.safra


class Counterparty(TenantAwareModel):
    grupo = models.ForeignKey(EconomicGroup, null=True, blank=True, on_delete=models.SET_NULL, related_name="contrapartes")
    contraparte = models.CharField(max_length=160, blank=True)
    obs = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "grupo"])]

    def __str__(self):
        parts = [str(self.grupo).strip() if self.grupo else "", str(self.contraparte).strip(), str(self.obs).strip()]
        for part in parts:
            if part:
                return part
        return f"Contraparte {self.pk}" if self.pk else "Contraparte"


class Broker(TenantAwareModel):
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "name"], name="uq_broker_name_tenant")]

    def __str__(self):
        return self.name


class GroupAccessRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        REJECTED = "rejected", "Rejeitado"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_access_requests",
    )
    group = models.ForeignKey(
        EconomicGroup,
        on_delete=models.CASCADE,
        related_name="access_requests",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_group_access_requests",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "group"],
                condition=models.Q(status="pending"),
                name="uq_pending_group_access_request",
            )
        ]

    def __str__(self):
        return f"{self.requester} -> {self.group}"


class SubGroupAccessRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        REJECTED = "rejected", "Rejeitado"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subgroup_access_requests",
    )
    subgroup = models.ForeignKey(
        SubGroup,
        on_delete=models.CASCADE,
        related_name="access_requests",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_subgroup_access_requests",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "subgroup"],
                condition=models.Q(status="pending"),
                name="uq_pending_subgroup_access_request",
            )
        ]

    def __str__(self):
        return f"{self.requester} -> {self.subgroup}"
