from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class PhysicalSale(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PARTIAL = "partial", "Partial"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    client = models.ForeignKey("clients.ClientAccount", on_delete=models.PROTECT, related_name="physical_sales")
    group = models.ForeignKey("clients.EconomicGroup", on_delete=models.PROTECT, related_name="physical_sales")
    subgroup = models.ForeignKey("clients.SubGroup", on_delete=models.PROTECT, related_name="physical_sales")
    crop = models.ForeignKey("catalog.Crop", on_delete=models.PROTECT, related_name="physical_sales")
    season = models.ForeignKey("clients.CropSeason", on_delete=models.PROTECT, related_name="physical_sales")
    counterparty = models.ForeignKey("clients.Counterparty", on_delete=models.PROTECT, related_name="physical_sales")
    trade_date = models.DateField()
    delivery_start = models.DateField()
    delivery_end = models.DateField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.ForeignKey("catalog.UnitOfMeasure", on_delete=models.PROTECT, related_name="physical_sales")
    price = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=10, default="BRL")
    basis = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    gross_value_brl = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    gross_value_usd = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True)
    external_id = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["-trade_date", "-created_at"]
        indexes = [models.Index(fields=["tenant", "client", "trade_date"]), models.Index(fields=["tenant", "status"])]

    def __str__(self):
        return f"{self.client} - {self.trade_date}"


class HedgeAllocation(TenantAwareModel):
    class AllocationType(models.TextChoices):
        DIRECT = "direct", "Direct"
        PARTIAL = "partial", "Partial"
        STRATEGIC = "strategic", "Strategic"

    physical_sale = models.ForeignKey(PhysicalSale, on_delete=models.CASCADE, related_name="allocations")
    derivative_operation = models.ForeignKey("derivatives.DerivativeOperation", on_delete=models.CASCADE, related_name="allocations")
    allocated_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    allocated_unit = models.ForeignKey("catalog.UnitOfMeasure", on_delete=models.PROTECT, related_name="hedge_allocations")
    allocation_type = models.CharField(max_length=20, choices=AllocationType.choices)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "physical_sale"]), models.Index(fields=["tenant", "derivative_operation"])]
