import json
import re
from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone

from .models import TradingViewWatchlistQuote

WATCHLIST_JSON_SCRIPT_RE = re.compile(
    r'<script type="application/prs\.init-data\+json">(.*?)</script>',
    re.DOTALL,
)
SECTION_PREFIX = "###"
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
DEFAULT_TRADINGVIEW_WATCHLIST_URL = "https://br.tradingview.com/watchlists/160853431/"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0 Safari/537.36",
    "Accept": "application/json,text/html,application/xhtml+xml",
}


class TradingViewScraperError(Exception):
    pass


def _fetch_text(url):
    request = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _post_json(url, payload):
    body = json.dumps(payload).encode("utf-8")
    headers = {**DEFAULT_HEADERS, "Content-Type": "application/json"}
    request = Request(url, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_watchlist_payload(html):
    for raw_json in WATCHLIST_JSON_SCRIPT_RE.findall(html):
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
        shared_watchlist = payload.get("sharedWatchlist") or {}
        watchlist = shared_watchlist.get("list")
        if watchlist:
            return watchlist
    raise TradingViewScraperError("Nao foi possivel localizar os dados da watchlist no HTML do TradingView.")


def _normalize_section_name(raw_value):
    cleaned = re.sub(r"[\u200b-\u200f\u2060-\u206f]", "", raw_value or "")
    cleaned = cleaned.replace(SECTION_PREFIX, "").strip()
    return cleaned


def _build_symbol_rows(watchlist):
    rows = []
    current_section = ""

    for sort_order, raw_symbol in enumerate(watchlist.get("symbols") or [], start=1):
        symbol = str(raw_symbol or "").strip()
        if not symbol:
            continue
        if symbol.startswith(SECTION_PREFIX):
            current_section = _normalize_section_name(symbol)
            continue

        provider, _, ticker = symbol.partition(":")
        rows.append(
            {
                "watchlist_id": str(watchlist.get("id") or ""),
                "watchlist_name": str(watchlist.get("name") or ""),
                "section_name": current_section,
                "symbol": symbol,
                "provider": provider,
                "ticker": ticker,
                "sort_order": sort_order,
            }
        )

    return rows


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


def _get_change_value_for_ticker(rows, quotes_by_symbol, target_ticker):
    normalized_target = str(target_ticker or "").strip().upper()
    for row in rows:
        if str(row.get("ticker") or "").strip().upper() != normalized_target:
            continue
        quote_data = quotes_by_symbol.get(row["symbol"], {})
        return quote_data.get("change_value")
    return None


def _get_quote_field_for_ticker(rows, quotes_by_symbol, target_ticker, field_name):
    normalized_target = str(target_ticker or "").strip().upper()
    for row in rows:
        if str(row.get("ticker") or "").strip().upper() != normalized_target:
            continue
        quote_data = quotes_by_symbol.get(row["symbol"], {})
        return quote_data.get(field_name)
    return None


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


def scrape_watchlist(source_url):
    html = _fetch_text(source_url)
    watchlist = _extract_watchlist_payload(html)
    rows = _build_symbol_rows(watchlist)
    quotes_by_symbol = _fetch_quotes_for_symbols([row["symbol"] for row in rows])
    synced_at = timezone.now()
    usdb_rl_change_value = _get_change_value_for_ticker(rows, quotes_by_symbol, "USDBRL")
    usdb_rl_change_percent = _get_quote_field_for_ticker(rows, quotes_by_symbol, "USDBRL", "change_percent")

    scraped_rows = []
    for row in rows:
        quote_data = quotes_by_symbol.get(row["symbol"], {})
        is_dol_ticker = str(row.get("ticker") or "").strip().upper().startswith("DOL")
        normalized_price = _normalize_price_for_ticker(row.get("symbol"), row.get("ticker"), quote_data.get("price"))
        if normalized_price is not None and is_dol_ticker and usdb_rl_change_value is not None:
            normalized_price += usdb_rl_change_value
        normalized_change_value = usdb_rl_change_value if is_dol_ticker else quote_data.get("change_value")
        normalized_change_percent = usdb_rl_change_percent if is_dol_ticker else quote_data.get("change_percent")
        scraped_rows.append(
            {
                **row,
                "source_url": source_url,
                "description": quote_data.get("description") or quote_data.get("name") or "",
                "price": normalized_price,
                "change_percent": normalized_change_percent,
                "change_value": normalized_change_value,
                "currency": quote_data.get("currency", ""),
                "instrument_type": quote_data.get("instrument_type", ""),
                "instrument_subtype": quote_data.get("instrument_subtype", ""),
                "synced_at": synced_at,
                "raw_data": _json_safe(quote_data),
            }
        )

    return {
        "watchlist_id": str(watchlist.get("id") or ""),
        "watchlist_name": str(watchlist.get("name") or ""),
        "symbols_found": len(rows),
        "quotes_resolved": sum(1 for row in scraped_rows if row["price"] is not None),
        "synced_at": synced_at,
        "rows": scraped_rows,
    }


@transaction.atomic
def sync_watchlist_to_db(source_url):
    payload = scrape_watchlist(source_url)
    TradingViewWatchlistQuote.objects.filter(source_url=source_url).delete()
    TradingViewWatchlistQuote.objects.bulk_create(
        [
            TradingViewWatchlistQuote(
                source_url=row["source_url"],
                watchlist_id=row["watchlist_id"],
                watchlist_name=row["watchlist_name"],
                section_name=row["section_name"],
                symbol=row["symbol"],
                provider=row["provider"],
                ticker=row["ticker"],
                description=row["description"],
                price=row["price"],
                change_percent=row["change_percent"],
                change_value=row["change_value"],
                currency=row["currency"],
                instrument_type=row["instrument_type"],
                instrument_subtype=row["instrument_subtype"],
                sort_order=row["sort_order"],
                synced_at=row["synced_at"],
                raw_data=row["raw_data"],
            )
            for row in payload["rows"]
        ]
    )
    return payload


def ensure_watchlist_is_fresh(source_url=DEFAULT_TRADINGVIEW_WATCHLIST_URL, max_age_minutes=10):
    latest_sync = (
        TradingViewWatchlistQuote.objects.filter(source_url=source_url)
        .order_by("-synced_at")
        .values_list("synced_at", flat=True)
        .first()
    )
    if latest_sync is None or latest_sync <= timezone.now() - timedelta(minutes=max_age_minutes):
        return sync_watchlist_to_db(source_url)
    return None


def parse_watchlist_id_from_url(source_url):
    path_parts = [part for part in urlparse(source_url).path.split("/") if part]
    return path_parts[-1] if path_parts else ""
