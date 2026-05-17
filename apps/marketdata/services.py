"""Cache de cotações históricas + cálculo de basis sob demanda.

Cotações históricas são imutáveis: o fechamento do contrato contínuo numa
data passada e o preço do dólar futuro numa data passada não mudam. Por isso
buscamos cada par (símbolo, data) no máximo uma vez na fonte externa e
guardamos em `HistoricalQuote`; as próximas leituras não fazem chamada
externa nenhuma. O basis é calculado na hora a partir do cache, então
continua dinâmico pela bolsa escolhida no momento da consulta.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.request import Request, urlopen

from django.utils import timezone

from apps.tradingview_scraper.contract_generator import MONTH_CODE
from apps.tradingview_scraper.services import (
    build_continuous_symbol,
    fetch_continuous_contract_price,
    fetch_dollar_future_quote,
)

from .models import HistoricalQuote

# Por quanto tempo um "miss" (sem cotação) é respeitado antes de rebuscar.
_MISS_TTL_SECONDS = 86400


def _cached_quote(symbol, quote_date, fetcher, source):
    """Retorna o fechamento de (symbol, quote_date), buscando só na 1ª vez."""
    row = HistoricalQuote.objects.filter(symbol=symbol, quote_date=quote_date).first()
    if row is not None:
        if row.close is not None:
            return row.close
        if (timezone.now() - row.fetched_at).total_seconds() < _MISS_TTL_SECONDS:
            return None
    price = fetcher()
    HistoricalQuote.objects.update_or_create(
        symbol=symbol,
        quote_date=quote_date,
        defaults={"close": price, "source": source},
    )
    return price


def get_board_continuous_close(exchange, quote_date):
    """Fechamento do contrato contínuo (1º) da bolsa na data informada."""
    if not exchange.tv_symbol_fmt:
        return None
    symbol = build_continuous_symbol(exchange.tv_symbol_fmt)
    return _cached_quote(
        symbol,
        quote_date,
        lambda: fetch_continuous_contract_price(exchange, quote_date.isoformat()),
        "continuous",
    )


def get_dollar_future_close(payment_date, trade_date):
    """Cotação do DOL futuro (vencimento do mês/ano do pagamento) na data de negociação."""
    symbol = f"BMFBOVESPA:DOL{MONTH_CODE[payment_date.month]}{payment_date.year}"
    return _cached_quote(
        symbol,
        trade_date,
        lambda: fetch_dollar_future_quote(payment_date.isoformat(), trade_date.isoformat()),
        "dol-future",
    )


def _ccy(value):
    s = str(value or "").strip().upper().replace(" ", "")
    if s in ("US$", "U$", "USD", "DOLAR", "DÓLAR", "DOLLAR", "$"):
        return "USD"
    if s in ("R$", "BRL", "REAL", "REAIS"):
        return "BRL"
    return s


def compute_sale_basis(sale, exchange):
    """basis = físico_convertido − cotação_bolsa (contínuo, na data de negociação).

    físico_convertido = preço ÷ fator                       (mesma moeda)
                      = preço ÷ dólar_futuro ÷ fator         (R$ contrato / U$ bolsa)

    Dólar futuro = contrato com vencimento anterior à data de pagamento,
    cotado na data de negociação.

    Retorna dict {basis, cotacao_bolsa, fisico_convertido, dolar_futuro} ou
    None se faltar algum insumo.
    """
    if sale.preco is None or not sale.data_negociacao:
        return None
    fator = exchange.fator_conversao_unidade_padrao_cultura
    if not fator:
        return None
    board = get_board_continuous_close(exchange, sale.data_negociacao)
    if board is None:
        return None

    fisico = Decimal(str(sale.preco))
    fator = Decimal(str(fator))
    dolar = None

    if _ccy(sale.moeda_contrato) == _ccy(exchange.moeda_bolsa):
        fisico_convertido = fisico / fator
    else:
        if not sale.data_pagamento:
            return None
        dolar = get_dollar_future_close(sale.data_pagamento, sale.data_negociacao)
        if not dolar:
            return None
        fisico_convertido = fisico / dolar / fator

    return {
        "basis": fisico_convertido - board,
        "cotacao_bolsa": board,
        "fisico_convertido": fisico_convertido,
        "dolar_futuro": dolar,
    }


_PTAX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}


def _fetch_ptax_close(date_str):
    """PTAX (dólar de fechamento, cotação de venda) do Banco Central na data.

    Usa a API Olinda do BCB. Em dia sem PTAX (fim de semana/feriado) anda
    para trás até 7 dias úteis. Retorna Decimal ou None.
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

    for back in range(0, 8):
        day = dt - timedelta(days=back)
        api_date = day.strftime("%m-%d-%Y")
        url = (
            "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
            f"CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao='{api_date}'"
            "&$top=1&$format=json"
        )
        try:
            request = Request(url, headers=_PTAX_HEADERS)
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            continue
        rows = data.get("value") or []
        if rows:
            venda = rows[0].get("cotacaoVenda")
            if venda is not None:
                try:
                    return Decimal(str(venda))
                except Exception:
                    return None
    return None


def get_ptax_usd_brl(quote_date):
    """PTAX USD/BRL (fechamento) na data, com cache imutável."""
    return _cached_quote(
        "PTAX:USDBRL",
        quote_date,
        lambda: _fetch_ptax_close(quote_date.isoformat()),
        "ptax",
    )
