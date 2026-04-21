from django.db import models


class Crop(models.Model):
    ativo = models.CharField(max_length=100, unique=True, null=True, blank=True)
    bolsa_ref = models.JSONField(default=list, blank=True)
    imagem = models.ImageField(upload_to="crops/", null=True, blank=True)
    unidade_fisico = models.ManyToManyField("catalog.Unit", blank=True, related_name="culturas")

    class Meta:
        ordering = ["ativo"]

    def __str__(self):
        return self.ativo


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
    ativo = models.CharField(max_length=100, blank=True)
    moeda_bolsa = models.CharField(max_length=40, blank=True)
    volume_padrao_contrato = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    unidade_bolsa = models.CharField(max_length=40, blank=True)
    moeda_cmdtye = models.CharField(max_length=20, blank=True)
    moeda_unidade_padrao = models.CharField(max_length=60, blank=True)
    fator_conversao_unidade_padrao_cultura = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    # Configuração TradingView — geração automática de contratos futuros
    tv_symbol_fmt  = models.CharField(max_length=80, blank=True,
        help_text="Formato do símbolo TradingView (ano 4 dígitos). Ex: BMFBOVESPA:DOL{month}{year4} ou CBOT:ZS{month}{year4}")
    tv_ticker_fmt  = models.CharField(max_length=60, blank=True,
        help_text="Formato do ticker no DB (ano 2 dígitos). Ex: DOL{month}{year} ou ZS{month}{year}")
    tv_months      = models.CharField(max_length=60, blank=True,
        help_text="Meses de vencimento separados por vírgula. Ex: 1,2,3,4,5,6,7,8,9,10,11,12")
    tv_n_contracts = models.PositiveSmallIntegerField(null=True, blank=True,
        help_text="Quantos vencimentos futuros manter simultaneamente.")

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class DerivativeOperationName(models.Model):
    nome = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome
