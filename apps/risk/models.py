from django.db import models

from apps.core.models import TenantAwareModel


class ExposurePosition(TenantAwareModel):
    client = models.ForeignKey("clients.ClientAccount", on_delete=models.PROTECT, related_name="exposure_positions")
    group = models.ForeignKey("clients.EconomicGroup", on_delete=models.PROTECT, related_name="exposure_positions")
    subgroup = models.ForeignKey("clients.SubGroup", on_delete=models.PROTECT, related_name="exposure_positions")
    crop = models.ForeignKey("catalog.Crop", on_delete=models.PROTECT, related_name="exposure_positions")
    season = models.ForeignKey("clients.CropSeason", on_delete=models.PROTECT, related_name="exposure_positions")
    reference_date = models.DateField()
    expected_production = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    physical_sold = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    hedge_volume = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    open_exposure = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    avg_physical_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    avg_hedge_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    mtm_brl = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    mtm_usd = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    hedge_ratio = models.DecimalField(max_digits=9, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ["-reference_date"]
        indexes = [models.Index(fields=["tenant", "reference_date"]), models.Index(fields=["tenant", "client", "season"])]
