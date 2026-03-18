from django.db import models


class Crop(models.Model):
    cultura = models.CharField(max_length=100, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["cultura"]

    def __str__(self):
        return self.cultura


class MarketInstrument(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    exchange = models.CharField(max_length=50, blank=True)
    underlying = models.CharField(max_length=80, blank=True)
    contract_size = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    quote_reference = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class PriceSource(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Currency(models.Model):
    nome = models.CharField(max_length=40, unique=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Unit(models.Model):
    nome = models.CharField(max_length=40, unique=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class PriceUnit(models.Model):
    nome = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Exchange(models.Model):
    nome = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome
