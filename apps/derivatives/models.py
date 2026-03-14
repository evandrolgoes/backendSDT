from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class DerivativeOperation(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    class Market(models.TextChoices):
        CME = "cme", "CME"
        B3 = "b3", "B3"
        OTC = "otc", "OTC"

    class Purpose(models.TextChoices):
        HEDGE = "hedge", "Hedge"
        SPECULATION = "speculation", "Speculation"
        PROTECTION = "protection", "Protection"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PARTIAL = "partial", "Partial"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    client = models.ForeignKey("clients.ClientAccount", on_delete=models.PROTECT, related_name="derivative_operations")
    group = models.ForeignKey("clients.EconomicGroup", on_delete=models.PROTECT, related_name="derivative_operations")
    subgroup = models.ForeignKey("clients.SubGroup", on_delete=models.PROTECT, related_name="derivative_operations")
    crop = models.ForeignKey("catalog.Crop", on_delete=models.PROTECT, related_name="derivative_operations")
    season = models.ForeignKey("clients.CropSeason", on_delete=models.PROTECT, related_name="derivative_operations")
    broker = models.ForeignKey("clients.Broker", on_delete=models.PROTECT, related_name="derivative_operations")
    counterparty = models.ForeignKey("clients.Counterparty", on_delete=models.PROTECT, related_name="derivative_operations")
    trade_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    settlement_date = models.DateField(null=True, blank=True)
    strategy_name = models.CharField(max_length=120)
    market = models.CharField(max_length=20, choices=Market.choices)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True)
    external_id = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["-trade_date", "-created_at"]
        indexes = [models.Index(fields=["tenant", "client", "trade_date"]), models.Index(fields=["tenant", "status"])]


class DerivativeLeg(models.Model):
    class Side(models.TextChoices):
        BUY = "buy", "Buy"
        SELL = "sell", "Sell"

    class LegType(models.TextChoices):
        FUTURE = "future", "Future"
        CALL = "call", "Call"
        PUT = "put", "Put"
        SWAP = "swap", "Swap"

    operation = models.ForeignKey(DerivativeOperation, on_delete=models.CASCADE, related_name="legs")
    instrument = models.ForeignKey("catalog.MarketInstrument", on_delete=models.PROTECT, related_name="legs")
    side = models.CharField(max_length=10, choices=Side.choices)
    leg_type = models.CharField(max_length=20, choices=LegType.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    contract_size = models.DecimalField(max_digits=18, decimal_places=4)
    strike = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    premium = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    premium_currency = models.CharField(max_length=10, blank=True)
    reference_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    settlement_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    settlement_date = models.DateField(null=True, blank=True)
    is_otc = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["operation", "instrument"])]


class MarkToMarketSnapshot(TenantAwareModel):
    derivative_operation = models.ForeignKey(DerivativeOperation, on_delete=models.CASCADE, related_name="mtm_snapshots")
    snapshot_date = models.DateField()
    gross_mtm = models.DecimalField(max_digits=18, decimal_places=2)
    premium_effect = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    net_mtm = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=10)
    details_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-snapshot_date"]
        indexes = [models.Index(fields=["tenant", "snapshot_date"])]


class CashSettlement(TenantAwareModel):
    class SettlementType(models.TextChoices):
        PREMIUM = "premium", "Premium"
        VARIATION = "variation", "Variation"
        FINAL = "final", "Final"

    derivative_operation = models.ForeignKey(DerivativeOperation, on_delete=models.CASCADE, related_name="cash_settlements")
    settlement_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=10)
    settlement_type = models.CharField(max_length=20, choices=SettlementType.choices)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-settlement_date"]
