from datetime import timedelta
from decimal import Decimal

from django.db import models

from apps.core.models import CreatedByMixin, TenantAwareModel, TimeStampedModel

# 1 arroba (@) = 15 kg de carcaca. Constante de mercado usada para converter
# peso vivo -> @ de carcaca (via rendimento de carcaca).
ARROBA_KG = Decimal("15")


class ConfinementDiet(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    """Dieta de confinamento (template reutilizavel por carteira).

    Define o consumo de materia seca e o custo por kg de MS. `pct_milho`
    identifica a fracao do custo da dieta exposta ao milho -- e o que conecta
    a perna racao ao hedge de milho (CCM/B3)."""

    nome = models.CharField(max_length=120)
    consumo_ms_kg_dia = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        verbose_name="Consumo de MS (kg/cabeca/dia)",
    )
    custo_ms_brl_kg = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        verbose_name="Custo da MS (R$/kg)",
    )
    pct_milho = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name="% do custo da dieta exposto ao milho (0-100)",
    )
    milho_kg_cabeca_dia = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        verbose_name="Milho (kg/cabeca/dia) -- p/ dimensionar hedge CCM",
    )
    obs = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]
        indexes = [models.Index(fields=["tenant", "nome"])]

    def __str__(self):
        return self.nome or f"Dieta {self.id}"


class ConfinementLot(TenantAwareModel, CreatedByMixin, TimeStampedModel):
    """Lote de confinamento (granularidade do MVP = medias do lote).

    Gera o volume de @ e o timing que alimentam a margem (crush), o hedge
    ratio e o gatilho de margem. Custos nao-racao reutilizam physical.BudgetCost
    /ActualCost; derivativos (BGI/CCM) reutilizam derivatives.DerivativeOperation;
    exposicao consolidada reutiliza risk.ExposurePosition -- amarrados pela
    mesma carteira (grupo/subgrupo/safra)."""

    class ReposicaoStatus(models.TextChoices):
        TRAVADA = "travada", "Travada (custo fixo)"
        EM_ABERTO = "em_aberto", "Em aberto (referencia + risco de base)"

    class ReposicaoUnidade(models.TextChoices):
        POR_ARROBA = "rs_arroba", "R$/@"
        POR_CABECA = "rs_cabeca", "R$/cabeca"
        POR_KG = "rs_kg", "R$/kg vivo"

    class Status(models.TextChoices):
        PLANEJADO = "planejado", "Planejado"
        EM_COCHO = "em_cocho", "Em cocho"
        ENCERRADO = "encerrado", "Encerrado"

    codigo_lote = models.CharField(max_length=120, blank=True)
    descricao = models.CharField(max_length=160, blank=True)

    # Carteira (mesmo padrao de derivatives/strategies)
    cliente = models.ForeignKey(
        "clients.ClientAccount", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="lotes_confinamento",
    )
    grupo = models.ForeignKey(
        "clients.EconomicGroup", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="lotes_confinamento",
    )
    subgrupo = models.ForeignKey(
        "clients.SubGroup", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="lotes_confinamento",
    )
    safra = models.ForeignKey(
        "clients.CropSeason", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="lotes_confinamento",
    )
    ativo = models.ForeignKey(
        "catalog.Crop", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="lotes_confinamento",
        verbose_name="Ativo (ex.: Boi Gordo)",
    )
    bolsa_ref = models.CharField(max_length=60, blank=True, verbose_name="Bolsa ref. (ex.: B3/BGI)")

    # Lote (medias)
    cabecas = models.PositiveIntegerField(null=True, blank=True)
    data_entrada = models.DateField(null=True, blank=True)
    peso_entrada_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Peso medio de entrada (kg/cabeca)",
    )
    gmd_kg_dia = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True,
        verbose_name="GMD projetado (kg/dia)",
    )
    dias_cocho = models.PositiveIntegerField(null=True, blank=True)
    peso_saida_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Peso medio de saida (kg/cabeca) -- derivado, override permitido",
    )
    peso_saida_manual = models.BooleanField(
        default=False, verbose_name="Peso de saida informado manualmente",
    )
    rendimento_carcaca = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name="Rendimento de carcaca (%) -- peso vivo -> @",
    )
    data_saida_projetada = models.DateField(
        null=True, blank=True,
        verbose_name="Data de saida projetada -- derivada (entrada + dias)",
    )
    dieta = models.ForeignKey(
        ConfinementDiet, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="lotes",
    )

    # Reposicao (boi magro de entrada) -- as duas situacoes por lote
    reposicao_status = models.CharField(
        max_length=20, blank=True, choices=ReposicaoStatus.choices,
        default=ReposicaoStatus.EM_ABERTO,
    )
    preco_reposicao = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        verbose_name="Preco reposicao (fixo se travada / referencia se em aberto)",
    )
    reposicao_unidade = models.CharField(
        max_length=12, blank=True, choices=ReposicaoUnidade.choices,
        default=ReposicaoUnidade.POR_CABECA,
    )
    regiao_base = models.CharField(
        max_length=80, blank=True,
        verbose_name="Regiao p/ base local vs ESALQ (reposicao em aberto)",
    )

    # Override manual do indicador a vista enquanto o provider CEPEA/ESALQ
    # nao existe (margem aberta).
    preco_boi_gordo_ref = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        verbose_name="Preco boi gordo a vista ref. (R$/@) -- override CEPEA",
    )

    status = models.CharField(
        max_length=20, blank=True, choices=Status.choices, default=Status.PLANEJADO,
    )
    obs = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "codigo_lote"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "subgrupo", "safra"]),
        ]

    def __str__(self):
        return self.codigo_lote or self.descricao or f"Lote confinamento {self.id}"

    # --- Derivados (nao persistir o que e calculavel) -------------------

    def _compute_peso_saida(self):
        if (
            self.peso_entrada_kg is not None
            and self.gmd_kg_dia is not None
            and self.dias_cocho is not None
        ):
            return Decimal(self.peso_entrada_kg) + Decimal(self.gmd_kg_dia) * Decimal(self.dias_cocho)
        return None

    def _compute_data_saida(self):
        if self.data_entrada is not None and self.dias_cocho is not None:
            return self.data_entrada + timedelta(days=int(self.dias_cocho))
        return None

    @property
    def arrobas_entrada_carcaca(self):
        """@ de carcaca equivalentes na entrada (peso vivo x rendimento)."""
        if not (self.cabecas and self.peso_entrada_kg and self.rendimento_carcaca):
            return None
        return (
            Decimal(self.cabecas)
            * Decimal(self.peso_entrada_kg)
            * Decimal(self.rendimento_carcaca) / Decimal("100")
            / ARROBA_KG
        )

    @property
    def arrobas_saida_carcaca(self):
        peso_saida = self.peso_saida_kg or self._compute_peso_saida()
        if not (self.cabecas and peso_saida and self.rendimento_carcaca):
            return None
        return (
            Decimal(self.cabecas)
            * Decimal(peso_saida)
            * Decimal(self.rendimento_carcaca) / Decimal("100")
            / ARROBA_KG
        )

    @property
    def arrobas_produzidas(self):
        entrada = self.arrobas_entrada_carcaca
        saida = self.arrobas_saida_carcaca
        if entrada is None or saida is None:
            return None
        return saida - entrada

    def save(self, *args, **kwargs):
        if not self.peso_saida_manual:
            self.peso_saida_kg = self._compute_peso_saida()
        self.data_saida_projetada = self._compute_data_saida()
        super().save(*args, **kwargs)
