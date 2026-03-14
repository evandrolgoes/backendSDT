from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel


class Strategy(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    client = models.ForeignKey("clients.ClientAccount", on_delete=models.PROTECT, related_name="strategies")
    crop = models.ForeignKey("catalog.Crop", on_delete=models.PROTECT, related_name="strategies")
    season = models.ForeignKey("clients.CropSeason", on_delete=models.PROTECT, related_name="strategies")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "client", "season", "name"], name="uq_strategy_name")]


class StrategyTrigger(models.Model):
    class TriggerType(models.TextChoices):
        PRICE = "price", "Price"
        FX = "fx", "FX"
        BASIS = "basis", "Basis"
        VOLUME = "volume", "Volume"

    class Operator(models.TextChoices):
        GT = "gt", ">"
        GTE = "gte", ">="
        LT = "lt", "<"
        LTE = "lte", "<="
        EQ = "eq", "="

    class ActionType(models.TextChoices):
        ALERT = "alert", "Alert"
        EXECUTE = "execute", "Execute"
        REVIEW = "review", "Review"

    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, related_name="triggers")
    name = models.CharField(max_length=120)
    trigger_type = models.CharField(max_length=20, choices=TriggerType.choices)
    operator = models.CharField(max_length=10, choices=Operator.choices)
    target_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    target_text = models.CharField(max_length=120, blank=True)
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    priority = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)


class TriggerEvent(models.Model):
    class Status(models.TextChoices):
        FIRED = "fired", "Fired"
        IGNORED = "ignored", "Ignored"
        EXECUTED = "executed", "Executed"

    trigger = models.ForeignKey(StrategyTrigger, on_delete=models.CASCADE, related_name="events")
    occurred_at = models.DateTimeField()
    reference_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
