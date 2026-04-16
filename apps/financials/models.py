from django.db import models

from apps.core.models import TenantAwareModel, TimeStampedModel


SCENARIO_CHOICES = [
    ("current", "Cenário Atual"),
    ("sim_1", "Simulação 1"),
    ("sim_2", "Simulação 2"),
    ("proj_2027", "Projeção 2027"),
    ("proj_2028", "Projeção 2028"),
]

TABLE_CHOICES = [
    ("balanco", "Balanço"),
    ("dre", "DRE"),
]


class FinancialEntry(TenantAwareModel, TimeStampedModel):
    """
    Stores individual financial statement cell values per (grupo, safra, scenario, table, key).

    For the DRE 'current' scenario, values are COMPUTED from operational models
    (PhysicalSale, ActualCost, etc.) and this table acts as an override/manual-entry
    store for the remaining scenarios and for all Balanço items.
    """

    grupo = models.ForeignKey(
        "clients.EconomicGroup",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="financial_entries",
    )
    safra = models.ForeignKey(
        "clients.CropSeason",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="financial_entries",
    )
    scenario = models.CharField(max_length=20, choices=SCENARIO_CHOICES, default="current")
    table = models.CharField(max_length=20, choices=TABLE_CHOICES)
    # Stable identifier for the row, e.g. "caixa_graos", "dre_vendas_liquidas"
    key = models.CharField(max_length=150)
    valor = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ["tenant", "grupo", "safra", "scenario", "table", "key"]
        ordering = ["table", "scenario", "key"]

    def __str__(self):
        return f"{self.table}/{self.key}/{self.scenario} = {self.valor}"
