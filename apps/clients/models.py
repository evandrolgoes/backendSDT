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

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "grupo"], name="uq_group_name_tenant")]
        indexes = [models.Index(fields=["tenant", "grupo"])]

    def __str__(self):
        return self.grupo


class SubGroup(TenantAwareModel):
    subgrupo = models.CharField(max_length=120, null=True, blank=True)

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
    subgrupo = models.ForeignKey(SubGroup, null=True, blank=True, on_delete=models.SET_NULL, related_name="contrapartes")
    grupo = models.ForeignKey(EconomicGroup, null=True, blank=True, on_delete=models.SET_NULL, related_name="contrapartes")
    obs = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "grupo"]), models.Index(fields=["tenant", "subgrupo"])]

    def __str__(self):
        return f"{self.grupo} / {self.subgrupo}"


class Broker(TenantAwareModel):
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "name"], name="uq_broker_name_tenant")]

    def __str__(self):
        return self.name
