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
    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name="groups")
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "client", "code"], name="uq_group_code_client")]
        indexes = [models.Index(fields=["tenant", "client"])]

    def __str__(self):
        return self.name


class SubGroup(TenantAwareModel):
    group = models.ForeignKey(EconomicGroup, on_delete=models.CASCADE, related_name="subgroups")
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "group", "code"], name="uq_subgroup_code_group")]
        indexes = [models.Index(fields=["tenant", "group"])]

    def __str__(self):
        return self.name


class CropSeason(TenantAwareModel):
    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name="seasons")
    crop = models.ForeignKey("catalog.Crop", on_delete=models.PROTECT, related_name="seasons")
    season_label = models.CharField(max_length=40)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "client", "crop", "season_label"], name="uq_crop_season")]
        indexes = [models.Index(fields=["tenant", "client", "crop"])]

    def __str__(self):
        return self.season_label


class Counterparty(TenantAwareModel):
    class CounterpartyType(models.TextChoices):
        BUYER = "buyer", "Buyer"
        BROKER = "broker", "Broker"
        BANK = "bank", "Bank"
        EXCHANGE = "exchange", "Exchange"

    name = models.CharField(max_length=120)
    counterparty_type = models.CharField(max_length=20, choices=CounterpartyType.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "name"], name="uq_counterparty_name_tenant")]

    def __str__(self):
        return self.name


class Broker(TenantAwareModel):
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "name"], name="uq_broker_name_tenant")]

    def __str__(self):
        return self.name
