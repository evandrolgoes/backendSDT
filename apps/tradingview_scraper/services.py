import json
import re
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone

from .models import TradingViewWatchlistQuote

SCAN_COLUMNS = [
    "name",
    "description",
    "close",
    "change",
    "change_abs",
    "currency",
    "type",
    "subtype",
]
SCAN_ENDPOINTS = ("brazil", "forex", "futures", "america", "global")
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0 Safari/537.36",
    "Accept": "application/json,text/html,application/xhtml+xml",
}
_async_refresh_lock = threading.Lock()
_async_refresh_running = False


def _post_json(url, payload):
    body = json.dumps(payload).encode("utf-8")
    headers = {**DEFAULT_HEADERS, "Content-Type": "application/json"}
    request = Request(url, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _to_decimal(value):
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _normalize_price_for_ticker(symbol, ticker, price):
    if price is None:
        return None
    if str(ticker or "").strip().upper().startswith("DOL"):
        return price / Decimal("1000")
    if str(symbol or "").strip().upper().startswith("CBOT"):
        return price / Decimal("100")
    return price


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _fetch_quotes_for_symbols(symbols, batch_size=50):
    resolved = OrderedDict()
    unresolved = list(OrderedDict.fromkeys(symbols))

    for endpoint in SCAN_ENDPOINTS:
        if not unresolved:
            break

        for index in range(0, len(unresolved), batch_size):
            batch = unresolved[index : index + batch_size]
            payload = {
                "symbols": {"tickers": batch, "query": {"types": []}},
                "columns": SCAN_COLUMNS,
            }

            try:
                response = _post_json(f"https://scanner.tradingview.com/{endpoint}/scan", payload)
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
                continue

            for item in response.get("data") or []:
                symbol = item.get("s")
                data = item.get("d") or []
                if not symbol:
                    continue
                resolved[symbol] = {
                    "name": data[0] if len(data) > 0 else "",
                    "description": data[1] if len(data) > 1 else "",
                    "price": _to_decimal(data[2] if len(data) > 2 else None),
                    "change_percent": _to_decimal(data[3] if len(data) > 3 else None),
                    "change_value": _to_decimal(data[4] if len(data) > 4 else None),
                    "currency": data[5] if len(data) > 5 and data[5] is not None else "",
                    "instrument_type": data[6] if len(data) > 6 and data[6] is not None else "",
                    "instrument_subtype": data[7] if len(data) > 7 and data[7] is not None else "",
                    "endpoint": endpoint,
                }

        unresolved = [symbol for symbol in unresolved if symbol not in resolved]

    return resolved


# ── Auto-generated contracts ─────────────────────────────────────────────────

from apps.catalog.models import Exchange  # noqa: E402
from .contract_generator import AUTO_SOURCE_URL, CONTRACTS_CONFIG, generate_active_symbols  # noqa: E402


def _build_contracts_config_from_db():
    """
    Constrói a lista de configurações de contratos a partir dos registros
    Exchange que tenham tv_symbol_fmt preenchido.
    Fallback: CONTRACTS_CONFIG hardcoded se nenhum Exchange estiver configurado.
    """
    config = []
    for ex in Exchange.objects.exclude(tv_symbol_fmt="").order_by("nome"):
        months_raw = ex.tv_months or ""
        months = [int(m.strip()) for m in months_raw.split(",") if m.strip().isdigit()]
        if not months:
            continue
        ticker_fmt = (ex.tv_ticker_fmt or "").strip() or ex.tv_symbol_fmt.split(":")[-1]
        config.append({
            "symbol_fmt": ex.tv_symbol_fmt.strip(),
            "ticker_fmt": ticker_fmt,
            "months":     months,
            "n":          ex.tv_n_contracts or 6,
            "section":    ex.nome,
        })

    # Símbolo fixo sempre presente (USD/BRL spot para cálculo de MTM)
    config.append({
        "symbol_fmt": "FX_IDC:USDBRL",
        "ticker_fmt": "USDBRL",
        "months":     None,
        "n":          1,
        "section":    "Câmbio Spot",
    })

    # Fallback: se nenhuma bolsa tiver TV configurado, usa config hardcoded
    if len(config) <= 1:
        return CONTRACTS_CONFIG

    return config


@transaction.atomic
def sync_auto_contracts():
    """
    Gera os contratos futuros ativos automaticamente e sincroniza os preços
    via TradingView Scanner API.

    Fluxo:
      1. generate_active_symbols() → lista de símbolos baseada na data atual
      2. _fetch_quotes_for_symbols() → preços via scanner.tradingview.com
      3. Normalização de preços (DOL ÷ 1000, CBOT ÷ 100)
      4. Ajuste DOL: adiciona variação do USDBRL ao preço DOL
      5. bulk_create no banco substituindo registros anteriores
    """
    contracts_config = _build_contracts_config_from_db()
    contract_rows = generate_active_symbols(contracts_config)
    symbols = [r["symbol"] for r in contract_rows]

    quotes_by_symbol = _fetch_quotes_for_symbols(symbols)
    synced_at = timezone.now()

    # Obtém variação do USDBRL para ajuste nos contratos DOL
    usdbrl_quote = quotes_by_symbol.get("FX_IDC:USDBRL") or {}
    usdbrl_change_value = usdbrl_quote.get("change_value")
    usdbrl_change_percent = usdbrl_quote.get("change_percent")

    db_rows = []
    for row in contract_rows:
        symbol = row["symbol"]
        ticker = row["ticker"]
        q = quotes_by_symbol.get(symbol) or {}

        is_dol = ticker.upper().startswith("DOL")

        normalized_price = _normalize_price_for_ticker(symbol, ticker, q.get("price"))
        if normalized_price is not None and is_dol and usdbrl_change_value is not None:
            normalized_price += usdbrl_change_value

        change_value = usdbrl_change_value if is_dol else q.get("change_value")
        change_percent = usdbrl_change_percent if is_dol else q.get("change_percent")

        provider, _, _ = symbol.partition(":")

        db_rows.append(
            TradingViewWatchlistQuote(
                source_url=AUTO_SOURCE_URL,
                watchlist_id="auto",
                watchlist_name="Contratos auto-gerados",
                section_name=row["section"],
                symbol=symbol,
                provider=provider,
                ticker=ticker,
                description=q.get("description") or q.get("name") or ticker,
                price=normalized_price,
                change_percent=change_percent,
                change_value=change_value,
                currency=q.get("currency") or "",
                instrument_type=q.get("instrument_type") or "",
                instrument_subtype=q.get("instrument_subtype") or "",
                sort_order=row["sort_order"],
                synced_at=synced_at,
                raw_data=_json_safe(q),
            )
        )

    TradingViewWatchlistQuote.objects.all().delete()
    TradingViewWatchlistQuote.objects.bulk_create(db_rows)

    return {
        "symbols_generated": len(symbols),
        "quotes_resolved": sum(1 for r in db_rows if r.price is not None),
        "synced_at": synced_at,
    }


def ensure_contracts_are_fresh(max_age_minutes=5):
    latest_sync = (
        TradingViewWatchlistQuote.objects.filter(source_url=AUTO_SOURCE_URL)
        .order_by("-synced_at")
        .values_list("synced_at", flat=True)
        .first()
    )
    if latest_sync is None or latest_sync <= timezone.now() - timedelta(minutes=max_age_minutes):
        return sync_auto_contracts()
    return None


def trigger_contracts_refresh_async(max_age_minutes=5):
    global _async_refresh_running

    latest_sync = (
        TradingViewWatchlistQuote.objects.filter(source_url=AUTO_SOURCE_URL)
        .order_by("-synced_at")
        .values_list("synced_at", flat=True)
        .first()
    )
    if latest_sync is not None and latest_sync > timezone.now() - timedelta(minutes=max_age_minutes):
        return False

    with _async_refresh_lock:
        if _async_refresh_running:
            return False
        _async_refresh_running = True

    def runner():
        global _async_refresh_running
        try:
            sync_auto_contracts()
        except Exception:
            pass
        finally:
            with _async_refresh_lock:
                _async_refresh_running = False

    threading.Thread(
        target=runner,
        name="tradingview-on-demand-refresh",
        daemon=True,
    ).start()
    return True


def build_continuous_symbol(tv_symbol_fmt):
    """Constrói o símbolo de contrato contínuo a partir do formato da bolsa.

    Ex.: "CBOT:ZS{month}{year4}" → "CBOT:ZS1!"
         "BMFBOVESPA:DOL{month}{year4}" → "BMFBOVESPA:DOL1!"
    """
    base = re.split(r"\{", tv_symbol_fmt)[0]
    return base + "1!"


# Prefixos de exchange que têm equivalente no Yahoo Finance como futuros contínuos
# O ticker base (ex: "ZS" de "CBOT:ZS{...}") → Yahoo Finance usa "{ticker}=F"
_YAHOO_FINANCE_EXCHANGE_PREFIXES = ("CBOT:", "CME:", "NYMEX:", "COMEX:", "ICE:")

_YAHOO_FINANCE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json,*/*",
}


def _fetch_yahoo_finance_price(tv_symbol_fmt, date_str):
    """Busca o preço de fechamento via Yahoo Finance para exchanges suportadas.

    Mapeia "CBOT:ZS{month}{year4}" → ticker Yahoo "ZS=F" (contrato contínuo).
    Retorna Decimal ou None.
    """
    from calendar import timegm
    from datetime import timedelta

    # Verifica se a exchange é suportada pelo Yahoo Finance
    upper_fmt = str(tv_symbol_fmt or "").upper()
    if not any(upper_fmt.startswith(prefix) for prefix in _YAHOO_FINANCE_EXCHANGE_PREFIXES):
        return None

    # Extrai o ticker base: "CBOT:ZS{month}{year4}" → "ZS"
    tv_ticker_base = re.split(r"\{", tv_symbol_fmt.split(":")[-1])[0]
    if not tv_ticker_base:
        return None

    yahoo_symbol = f"{tv_ticker_base}=F"

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

    # Busca uma janela de 5 dias para cobrir fins de semana e feriados
    period1 = timegm(dt.timetuple())
    period2 = timegm((dt + timedelta(days=5)).timetuple())

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        f"?interval=1d&period1={period1}&period2={period2}"
    )
    try:
        request = Request(url, headers=_YAHOO_FINANCE_HEADERS)
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    try:
        result = (data.get("chart") or {}).get("result") or []
        if not result:
            return None
        timestamps = result[0].get("timestamp") or []
        closes = (result[0].get("indicators") or {}).get("quote", [{}])[0].get("close") or []
        if not timestamps or not closes:
            return None
        # Retorna o fechamento do dia mais próximo a partir da data solicitada
        target_ts = period1
        best_close = None
        best_diff = None
        for ts, close in zip(timestamps, closes):
            if ts is None or close is None:
                continue
            diff = abs(ts - target_ts)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best_close = close
        if best_close is None:
            return None
        # Yahoo Finance retorna CBOT em centavos (USX) — normaliza ÷ 100
        raw_price = _to_decimal(best_close)
        return _normalize_price_for_ticker(tv_symbol_fmt, tv_ticker_base, raw_price)
    except Exception:
        return None


def _fetch_scanner_price_for_continuous(tv_symbol_fmt):
    """Busca o preço atual do contrato contínuo via scanner.tradingview.com.

    Usado como fallback para exchanges sem histórico gratuito (ex: B3).
    Retorna Decimal ou None.
    """
    continuous_symbol = build_continuous_symbol(tv_symbol_fmt)
    ticker_base = re.split(r"\{", tv_symbol_fmt.split(":")[-1])[0]
    quotes = _fetch_quotes_for_symbols([continuous_symbol])
    quote = quotes.get(continuous_symbol) or {}
    raw_price = quote.get("price")
    if raw_price is None:
        return None
    return _normalize_price_for_ticker(continuous_symbol, ticker_base, raw_price)


def fetch_continuous_contract_price(exchange, date_str):
    """Busca o preço de fechamento do contrato contínuo da bolsa na data informada.

    Estratégia:
    1. Para exchanges CBOT/CME/NYMEX/COMEX/ICE: busca histórico no Yahoo Finance.
    2. Para demais exchanges (ex: B3): usa o scanner do TradingView (preço atual).

    Aplica a mesma normalização de preços usada nos contratos do scanner.

    Args:
        exchange: instância de Exchange (catalog.models)
        date_str: data no formato "YYYY-MM-DD"

    Returns:
        Decimal com o preço ou None se não encontrado.
    """
    if not exchange.tv_symbol_fmt:
        return None

    # Tenta Yahoo Finance para exchanges com histórico gratuito
    price = _fetch_yahoo_finance_price(exchange.tv_symbol_fmt, date_str)
    if price is not None:
        return price

    # Fallback: scanner TradingView (preço atual — sem histórico)
    return _fetch_scanner_price_for_continuous(exchange.tv_symbol_fmt)
