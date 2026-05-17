"""Motor de margem do confinamento (crush de 3 pernas).

Servico puro (sem I/O) que, dado um ConfinementLot + os precos de entrada,
calcula DUAS margens lado a lado:

  - margem ABERTA   : receita pelo boi gordo a vista (CEPEA/ESALQ +/- base
                      regional). Override manual em lote.preco_boi_gordo_ref
                      enquanto o provider CEPEA nao existe.
  - margem TRAVAVEL : receita pela curva BGI/B3 interpolada p/ a data de
                      saida + racao pela curva de milho (CCM/B3).

Formula (R$):
    Receita_boi  = @_carcaca_saida x preco_boi
  - Reposicao    = funcao(reposicao_unidade, preco_reposicao | ref +/- base)
  - Racao        = consumo_MS_total x custo_MS
  - Operacional  = SUM(physical.BudgetCost da carteira)   [passado em inputs]
  - Encargos     = receita x encargos_pct (Funrural/frete/comissao)
  = MARGEM  ->  R$/@ produzida, R$/cabeca, R$/lote, e % (margem/custo)

Pontos de plug de dado externo (TODO, marcados PLUG:):
  - PLUG-BGI    : curva BGI/B3 interpolada p/ data_saida_projetada
  - PLUG-CEPEA  : indicador a vista CEPEA/ESALQ do boi gordo (+/- base)
  - PLUG-CCM    : curva de milho B3 p/ a perna racao travavel
  - PLUG-CUSTO  : agregacao de physical.BudgetCost/ActualCost por carteira
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

ZERO = Decimal("0")


def _D(value) -> Optional[Decimal]:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass
class MarginInputs:
    """Precos/parametros de entrada do calculo.

    Tudo em R$. Precos de boi em R$/@ de carcaca (mesma base do indicador
    ESALQ e do contrato BGI)."""

    # Boi gordo (receita)
    preco_boi_aberto: Optional[Decimal] = None      # PLUG-CEPEA (a vista)
    preco_boi_travavel: Optional[Decimal] = None     # PLUG-BGI (curva p/ data saida)
    base_regional: Decimal = ZERO                    # +/- aplicado ao boi a vista

    # Racao (perna milho hedgeavel via CCM)
    custo_ms_aberto_brl_kg: Optional[Decimal] = None     # sobrepoe dieta.custo_ms_brl_kg
    custo_ms_travavel_brl_kg: Optional[Decimal] = None    # PLUG-CCM

    # Reposicao quando lote.reposicao_status == "em_aberto"
    preco_reposicao_aberto: Optional[Decimal] = None

    # Custos nao-racao agregados da carteira (R$/lote) -- PLUG-CUSTO
    custo_operacional_total: Decimal = ZERO

    # Encargos sobre a receita (Funrural + frete + comissao), fracao 0-1
    encargos_pct: Decimal = ZERO


@dataclass
class MarginBreakdown:
    cenario: str  # "aberta" | "travavel"
    receita_boi: Decimal = ZERO
    custo_reposicao: Decimal = ZERO
    custo_racao: Decimal = ZERO
    custo_operacional: Decimal = ZERO
    encargos: Decimal = ZERO
    custo_total: Decimal = ZERO
    margem_lote: Decimal = ZERO
    margem_por_arroba: Optional[Decimal] = None
    margem_por_cabeca: Optional[Decimal] = None
    margem_pct_custo: Optional[Decimal] = None
    racao_milho_hedgeavel: Decimal = ZERO  # parte da racao exposta ao milho
    reposicao_em_aberto: bool = False      # True => carrega risco de base
    avisos: list = field(default_factory=list)


@dataclass
class MarginResult:
    aberta: MarginBreakdown
    travavel: MarginBreakdown
    arrobas_saida_carcaca: Optional[Decimal] = None
    arrobas_produzidas: Optional[Decimal] = None
    cabecas: Optional[int] = None


class ConfinementMarginService:
    """Calcula a margem de um lote. Nao faz I/O: precos vem em MarginInputs."""

    def __init__(self, lot, inputs: MarginInputs):
        self.lot = lot
        self.inputs = inputs

    # --- pernas de custo -------------------------------------------------

    def _custo_reposicao(self, preco_unitario: Optional[Decimal]) -> Decimal:
        lot = self.lot
        preco = _D(preco_unitario)
        if preco is None or not lot.cabecas:
            return ZERO
        cabecas = Decimal(lot.cabecas)
        unidade = lot.reposicao_unidade
        if unidade == lot.ReposicaoUnidade.POR_CABECA:
            return cabecas * preco
        if unidade == lot.ReposicaoUnidade.POR_KG:
            if not lot.peso_entrada_kg:
                return ZERO
            return cabecas * Decimal(lot.peso_entrada_kg) * preco
        # R$/@ -> usa @ de carcaca equivalentes na entrada
        arrobas_entrada = lot.arrobas_entrada_carcaca
        return (arrobas_entrada or ZERO) * preco

    def _custo_racao(self, custo_ms_brl_kg: Optional[Decimal]):
        """Retorna (custo_racao_total, parte_exposta_ao_milho)."""
        lot = self.lot
        dieta = lot.dieta
        if dieta is None or not lot.cabecas or not lot.dias_cocho:
            return ZERO, ZERO
        consumo_dia = _D(dieta.consumo_ms_kg_dia)
        custo_ms = _D(custo_ms_brl_kg) or _D(dieta.custo_ms_brl_kg)
        if consumo_dia is None or custo_ms is None:
            return ZERO, ZERO
        consumo_total = Decimal(lot.cabecas) * consumo_dia * Decimal(lot.dias_cocho)
        custo_racao = consumo_total * custo_ms
        pct_milho = _D(dieta.pct_milho)
        milho_parte = custo_racao * (pct_milho / Decimal("100")) if pct_milho else ZERO
        return custo_racao, milho_parte

    # --- montagem de um cenario -----------------------------------------

    def _build(self, cenario: str, preco_boi: Optional[Decimal],
               custo_ms: Optional[Decimal]) -> MarginBreakdown:
        lot = self.lot
        out = MarginBreakdown(cenario=cenario)

        arrobas_saida = lot.arrobas_saida_carcaca
        if preco_boi is None:
            out.avisos.append("Preco do boi gordo ausente para o cenario.")
        if arrobas_saida is None:
            out.avisos.append("Faltam dados do lote (cabecas/peso/rendimento) p/ @ de saida.")

        out.receita_boi = (arrobas_saida or ZERO) * (_D(preco_boi) or ZERO)

        # Reposicao: travada => preco fixo do lote (sem risco nas 2 telas);
        # em aberto => referencia +/- base (carrega risco de base).
        if lot.reposicao_status == lot.ReposicaoStatus.TRAVADA:
            out.custo_reposicao = self._custo_reposicao(lot.preco_reposicao)
        else:
            out.reposicao_em_aberto = True
            ref = self.inputs.preco_reposicao_aberto or lot.preco_reposicao
            out.custo_reposicao = self._custo_reposicao(ref)
            out.avisos.append("Reposicao em aberto: margem carrega risco de base (cross-hedge BGI).")

        out.custo_racao, out.racao_milho_hedgeavel = self._custo_racao(custo_ms)
        out.custo_operacional = _D(self.inputs.custo_operacional_total) or ZERO
        out.encargos = out.receita_boi * (_D(self.inputs.encargos_pct) or ZERO)

        out.custo_total = (
            out.custo_reposicao + out.custo_racao
            + out.custo_operacional + out.encargos
        )
        out.margem_lote = out.receita_boi - out.custo_total

        produzidas = lot.arrobas_produzidas
        if produzidas and produzidas != ZERO:
            out.margem_por_arroba = out.margem_lote / produzidas
        if lot.cabecas:
            out.margem_por_cabeca = out.margem_lote / Decimal(lot.cabecas)
        if out.custo_total and out.custo_total != ZERO:
            out.margem_pct_custo = out.margem_lote / out.custo_total * Decimal("100")
        return out

    def compute(self) -> MarginResult:
        inp = self.inputs

        preco_boi_aberto = _D(inp.preco_boi_aberto)
        if preco_boi_aberto is None and self.lot.preco_boi_gordo_ref is not None:
            preco_boi_aberto = _D(self.lot.preco_boi_gordo_ref)
        if preco_boi_aberto is not None:
            preco_boi_aberto = preco_boi_aberto + (_D(inp.base_regional) or ZERO)

        aberta = self._build("aberta", preco_boi_aberto, inp.custo_ms_aberto_brl_kg)
        travavel = self._build(
            "travavel", _D(inp.preco_boi_travavel), inp.custo_ms_travavel_brl_kg
        )

        return MarginResult(
            aberta=aberta,
            travavel=travavel,
            arrobas_saida_carcaca=self.lot.arrobas_saida_carcaca,
            arrobas_produzidas=self.lot.arrobas_produzidas,
            cabecas=self.lot.cabecas,
        )
