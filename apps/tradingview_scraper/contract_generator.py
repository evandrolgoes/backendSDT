"""
Geração automática de contratos futuros ativos.

Substitui a dependência da watchlist do TradingView: em vez de raspar uma lista
mantida manualmente, os símbolos são calculados a partir da data atual e dos
calendários de vencimento de cada commodity.

Para adicionar um novo contrato, basta incluir uma entrada em CONTRACTS_CONFIG.

Formatos de símbolo aceitos pela Scanner API do TradingView:
  - CBOT:ZSK2026   (bolsa:root + mês + ano 4 dígitos)
  - BMFBOVESPA:DOLM2026  (B3 usa prefixo BMFBOVESPA, não BMF)
  - FX_IDC:USDBRL  (spot, sem vencimento)

Formatos de ticker (armazenados no DB, sem provider):
  - ZSK26, DOLM26  (2 dígitos no ano – compatível com contrato_derivativo nas operações)
"""

import calendar
import datetime

# Código de mês padrão (CBOT / CME / B3)
# F=Jan  G=Feb  H=Mar  J=Apr  K=May  M=Jun
# N=Jul  Q=Aug  U=Sep  V=Oct  X=Nov  Z=Dec
MONTH_CODE = {
    1: "F", 2: "G",  3: "H", 4: "J",  5: "K",  6: "M",
    7: "N", 8: "Q",  9: "U", 10: "V", 11: "X", 12: "Z",
}

# A partir deste dia o contrato do mês de entrega é considerado vencido
# para produtos de rolagem "mid" (grãos CBOT / milho B3 — último pregão ~dia 14).
ROLL_MID_DAY = 15

# Regra de rolagem inferida pelo root do contrato, usada quando a config
# (montada a partir do DB) não traz o campo "roll" explícito:
#   "mid" – vence no meio do mês (today.day >= ROLL_MID_DAY)
#   "eom" – vence no último dia útil do mês de entrega
ROLL_BY_ROOT = {
    "ZS": "mid", "ZW": "mid", "ZC": "mid", "ZM": "mid",
    "ZL": "mid", "ZO": "mid", "ZR": "mid", "KE": "mid",
    "CCM": "mid",
    "DOL": "eom", "WDO": "eom", "BGI": "eom",
}


def _extract_root(symbol_fmt):
    """'CBOT:ZS{month}{year4}' → 'ZS'."""
    tail = str(symbol_fmt or "").split(":")[-1]
    brace = tail.find("{")
    return tail[:brace] if brace != -1 else tail


def _resolve_roll(cfg):
    """Regra de rolagem: cfg['roll'] explícito tem prioridade; caso contrário
    infere pelo root do símbolo (cobre a config montada a partir do DB)."""
    return cfg.get("roll") or ROLL_BY_ROOT.get(_extract_root(cfg.get("symbol_fmt", "")))


def _last_business_day(year, month):
    last_day = calendar.monthrange(year, month)[1]
    day = datetime.date(year, month, last_day)
    while day.weekday() >= 5:  # 5 = sábado, 6 = domingo
        day -= datetime.timedelta(days=1)
    return day


def _current_month_expired(roll, today):
    """True se o contrato do mês corrente de entrega já venceu."""
    if roll == "mid":
        return today.day >= ROLL_MID_DAY
    if roll == "eom":
        return today > _last_business_day(today.year, today.month)
    return False

# Cada entrada define:
#   symbol_fmt  – formato do símbolo TradingView (usa {year4} = 4 dígitos)
#                 ex: "BMFBOVESPA:DOL{month}{year4}"
#   ticker_fmt  – formato do ticker no DB (usa {year} = 2 dígitos)
#                 ex: "DOL{month}{year}"  →  compatível com contrato_derivativo
#   months      – lista de meses de vencimento (1=Jan … 12=Dez)
#                 None = símbolo fixo (sem vencimento, ex: spot)
#   n           – quantos vencimentos futuros manter simultaneamente
#   section     – nome da seção para exibição / filtragem
#   roll        – regra de rolagem do mês de entrega (opcional):
#                 "mid" = vence ~meio do mês (dia >= ROLL_MID_DAY)
#                 "eom" = vence no último dia útil do mês
#                 ausente = inferido pelo root via ROLL_BY_ROOT
CONTRACTS_CONFIG = [
    # ── DOLAR FWD — nome deve bater com Exchange.nome no banco ───────────────
    {
        "symbol_fmt": "BMFBOVESPA:DOL{month}{year4}",
        "ticker_fmt": "DOL{month}{year}",
        "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "n": 60,
        "section": "DOLAR FWD",
        "roll": "eom",
    },
    {
        "symbol_fmt": "BMFBOVESPA:WDO{month}{year4}",
        "ticker_fmt": "WDO{month}{year}",
        "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "n": 60,
        "section": "DOLAR FWD",
        "roll": "eom",
    },
    # ── MILHO B3 ─────────────────────────────────────────────────────────────
    {
        "symbol_fmt": "BMFBOVESPA:CCM{month}{year4}",
        "ticker_fmt": "CCM{month}{year}",
        "months": [3, 5, 7, 9, 11],
        "n": 6,
        "section": "MILHO B3",
        "roll": "mid",
    },
    # ── SOJA CBOT ────────────────────────────────────────────────────────────
    {
        "symbol_fmt": "CBOT:ZS{month}{year4}",
        "ticker_fmt": "ZS{month}{year}",
        "months": [1, 3, 5, 7, 8, 9, 11],
        "n": 6,
        "section": "SOJA CBOT",
        "roll": "mid",
    },
    # ── TRIGO CBOT ───────────────────────────────────────────────────────────
    {
        "symbol_fmt": "CBOT:ZW{month}{year4}",
        "ticker_fmt": "ZW{month}{year}",
        "months": [3, 5, 7, 9, 12],
        "n": 6,
        "section": "TRIGO CBOT",
        "roll": "mid",
    },
    # ── Extras (MTM / cotações) — sem bolsa vinculada ────────────────────────
    {
        "symbol_fmt": "BMFBOVESPA:BGI{month}{year4}",   # Boi Gordo B3
        "ticker_fmt": "BGI{month}{year}",
        "months": [2, 4, 6, 8, 10, 12],
        "n": 4,
        "section": "Extras",
        "roll": "eom",
    },
    {
        "symbol_fmt": "CBOT:ZC{month}{year4}",   # Milho CBOT
        "ticker_fmt": "ZC{month}{year}",
        "months": [3, 5, 7, 9, 12],
        "n": 4,
        "section": "Extras",
        "roll": "mid",
    },
    # ── Câmbio Spot ──────────────────────────────────────────────────────────
    {
        "symbol_fmt": "FX_IDC:USDBRL",          # símbolo fixo, sem vencimento
        "ticker_fmt": "USDBRL",
        "months": None,
        "n": 1,
        "section": "Câmbio Spot",
    },
]

# Símbolo especial para a origem dos dados no banco (substitui a URL da watchlist)
AUTO_SOURCE_URL = "auto-generated"


def generate_active_symbols(contracts_config=None, reference_date=None):
    """
    Retorna lista de dicts com os contratos ativos a partir de *reference_date*
    (padrão: hoje). Cada dict contém:
        symbol      – símbolo TradingView (ano 4 dígitos)  ex: "BMFBOVESPA:DOLM2026"
        ticker      – ticker curto (ano 2 dígitos)         ex: "DOLM26"
        section     – nome da seção                        ex: "DOLAR FWD"
        sort_order  – inteiro para ordenação

    Formatos disponíveis em symbol_fmt / ticker_fmt:
        {month}   – letra do mês (F, G, H, J, K, M, N, Q, U, V, X, Z)
        {year}    – últimos 2 dígitos do ano  ex: "26"
        {year4}   – ano completo com 4 dígitos ex: "2026"

    Args:
        contracts_config: lista de dicts com symbol_fmt, ticker_fmt, months, n, section.
                          Se None, usa CONTRACTS_CONFIG hardcoded como fallback.
        reference_date:   data de referência para cálculo dos vencimentos (padrão: hoje).
    """
    config = contracts_config if contracts_config is not None else CONTRACTS_CONFIG
    today = reference_date or datetime.date.today()
    result = []
    sort_order = 0

    for cfg in config:
        if cfg["months"] is None:
            # Símbolo fixo — sem geração por vencimento
            result.append({
                "symbol": cfg["symbol_fmt"],
                "ticker": cfg["ticker_fmt"],
                "section": cfg["section"],
                "sort_order": sort_order,
            })
            sort_order += 1
            continue

        roll = _resolve_roll(cfg)
        year = today.year
        month = today.month
        found = 0
        iterations = 0

        while found < cfg["n"] and iterations < 120:
            iterations += 1
            is_current_month = year == today.year and month == today.month
            expired = is_current_month and _current_month_expired(roll, today)
            if month in cfg["months"] and not expired:
                m_code = MONTH_CODE[month]
                y2 = str(year)[-2:]
                y4 = str(year)
                result.append({
                    "symbol": cfg["symbol_fmt"].format(month=m_code, year=y2, year4=y4),
                    "ticker": cfg["ticker_fmt"].format(month=m_code, year=y2, year4=y4),
                    "section": cfg["section"],
                    "sort_order": sort_order,
                })
                sort_order += 1
                found += 1
            month += 1
            if month > 12:
                month = 1
                year += 1

    return result
