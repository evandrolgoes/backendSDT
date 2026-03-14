from django.db import models


class Crop(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UnitOfMeasure(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    conversion_to_kg = models.DecimalField(max_digits=18, decimal_places=6)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.code


class MarketInstrument(models.Model):
    class AssetClass(models.TextChoices):
        FUTURE = "future", "Future"
        OPTION = "option", "Option"
        SWAP = "swap", "Swap"
        OTC = "otc", "OTC"

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    asset_class = models.CharField(max_length=20, choices=AssetClass.choices)
    exchange = models.CharField(max_length=50, blank=True)
    underlying = models.CharField(max_length=80, blank=True)
    contract_size = models.DecimalField(max_digits=18, decimal_places=4)
    quote_currency = models.CharField(max_length=10, default="USD")

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class PriceSource(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
