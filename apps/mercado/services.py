import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone


FUND_POSITION_SERIES = {
    "soja": {
        "id": "soja",
        "label": "Soja",
        "exchange_label": "CBOT",
        "market_name": "SOYBEANS - CHICAGO BOARD OF TRADE",
        "yahoo_symbol": "ZS=F",
        "start_date": "2020-01-01",
    },
    "milho": {
        "id": "milho",
        "label": "Milho",
        "exchange_label": "CBOT",
        "market_name": "CORN - CHICAGO BOARD OF TRADE",
        "yahoo_symbol": "ZC=F",
        "start_date": "2020-01-01",
    },
    "trigo-srw": {
        "id": "trigo-srw",
        "label": "Trigo SRW",
        "exchange_label": "CBOT",
        "market_name": "WHEAT-SRW - CHICAGO BOARD OF TRADE",
        "yahoo_symbol": "ZW=F",
        "start_date": "2020-01-01",
    },
    "trigo-hrw": {
        "id": "trigo-hrw",
        "label": "Trigo HRW",
        "exchange_label": "KCBT",
        "market_name": "WHEAT-HRW - CHICAGO BOARD OF TRADE",
        "yahoo_symbol": "KE=F",
        "start_date": "2020-01-01",
    },
    "farelo-soja": {
        "id": "farelo-soja",
        "label": "Farelo de Soja",
        "exchange_label": "CBOT",
        "market_name": "SOYBEAN MEAL - CHICAGO BOARD OF TRADE",
        "yahoo_symbol": "ZM=F",
        "start_date": "2020-01-01",
    },
    "oleo-soja": {
        "id": "oleo-soja",
        "label": "Oleo de Soja",
        "exchange_label": "CBOT",
        "market_name": "SOYBEAN OIL - CHICAGO BOARD OF TRADE",
        "yahoo_symbol": "ZL=F",
        "start_date": "2020-01-01",
    },
    "acucar": {
        "id": "acucar",
        "label": "Acucar",
        "exchange_label": "ICE",
        "market_name": "SUGAR NO. 11 - ICE FUTURES U.S.",
        "yahoo_symbol": "SB=F",
        "start_date": "2020-01-01",
    },
    "cafe": {
        "id": "cafe",
        "label": "Cafe",
        "exchange_label": "ICE",
        "market_name": "COFFEE C - ICE FUTURES U.S.",
        "yahoo_symbol": "KC=F",
        "start_date": "2020-01-01",
    },
    "cacau": {
        "id": "cacau",
        "label": "Cacau",
        "exchange_label": "ICE",
        "market_name": "COCOA - ICE FUTURES U.S.",
        "yahoo_symbol": "CC=F",
        "start_date": "2020-01-01",
    },
    "algodao": {
        "id": "algodao",
        "label": "Algodao",
        "exchange_label": "ICE",
        "market_name": "COTTON NO. 2 - ICE FUTURES U.S.",
        "yahoo_symbol": "CT=F",
        "start_date": "2020-01-01",
    },
    "suco-laranja": {
        "id": "suco-laranja",
        "label": "Suco de Laranja",
        "exchange_label": "ICE",
        "market_name": "ORANGE JUICE - ICE FUTURES U.S.",
        "yahoo_symbol": "OJ=F",
        "start_date": "2020-01-01",
    },
    "arroz": {
        "id": "arroz",
        "label": "Arroz",
        "exchange_label": "CBOT",
        "market_name": "ROUGH RICE - CHICAGO BOARD OF TRADE",
        "yahoo_symbol": "ZR=F",
        "start_date": "2020-01-01",
    },
    "aveia": {
        "id": "aveia",
        "label": "Aveia",
        "exchange_label": "CBOT",
        "market_name": "OATS - CHICAGO BOARD OF TRADE",
        "yahoo_symbol": "ZO=F",
        "start_date": "2020-01-01",
    },
    "boi-gordo": {
        "id": "boi-gordo",
        "label": "Boi Gordo",
        "exchange_label": "CME",
        "market_name": "LIVE CATTLE - CHICAGO MERCANTILE EXCHANGE",
        "yahoo_symbol": "LE=F",
        "start_date": "2020-01-01",
    },
    "gado-reposicao": {
        "id": "gado-reposicao",
        "label": "Gado de Reposicao",
        "exchange_label": "CME",
        "market_name": "FEEDER CATTLE - CHICAGO MERCANTILE EXCHANGE",
        "yahoo_symbol": "GF=F",
        "start_date": "2020-01-01",
    },
    "suino": {
        "id": "suino",
        "label": "Suino Magro",
        "exchange_label": "CME",
        "market_name": "LEAN HOGS - CHICAGO MERCANTILE EXCHANGE",
        "yahoo_symbol": "HE=F",
        "start_date": "2020-01-01",
    },
    "leite": {
        "id": "leite",
        "label": "Leite Classe III",
        "exchange_label": "CME",
        "market_name": "CLASS III MILK - CHICAGO MERCANTILE EXCHANGE",
        "yahoo_symbol": "DC=F",
        "start_date": "2020-01-01",
    },
    "petroleo-wti": {
        "id": "petroleo-wti",
        "label": "Petroleo WTI",
        "exchange_label": "NYMEX",
        "market_name": "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE",
        "yahoo_symbol": "CL=F",
        "start_date": "2020-01-01",
    },
    "petroleo-brent": {
        "id": "petroleo-brent",
        "label": "Petroleo Brent",
        "exchange_label": "ICE",
        "market_name": "BRENT CRUDE OIL LAST DAY FINANCIAL - ICE FUTURES EUROPE",
        "yahoo_symbol": "BZ=F",
        "start_date": "2020-01-01",
    },
    "ouro": {
        "id": "ouro",
        "label": "Ouro",
        "exchange_label": "COMEX",
        "market_name": "GOLD - COMMODITY EXCHANGE INC.",
        "yahoo_symbol": "GC=F",
        "start_date": "2020-01-01",
    },
    "gas-natural": {
        "id": "gas-natural",
        "label": "Gas Natural",
        "exchange_label": "NYMEX",
        "market_name": "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE",
        "yahoo_symbol": "NG=F",
        "start_date": "2020-01-01",
    },
    "ouro": {
        "id": "ouro",
        "label": "Ouro",
        "exchange_label": "COMEX",
        "market_name": "GOLD - COMMODITY EXCHANGE INC.",
        "yahoo_symbol": "GC=F",
        "start_date": "2020-01-01",
    },
    "prata": {
        "id": "prata",
        "label": "Prata",
        "exchange_label": "COMEX",
        "market_name": "SILVER - COMMODITY EXCHANGE INC.",
        "yahoo_symbol": "SI=F",
        "start_date": "2020-01-01",
    },
    "cobre": {
        "id": "cobre",
        "label": "Cobre",
        "exchange_label": "COMEX",
        "market_name": "COPPER-GRADE #1 - COMMODITY EXCHANGE INC.",
        "yahoo_symbol": "HG=F",
        "start_date": "2020-01-01",
    },
    "real-brasileiro": {
        "id": "real-brasileiro",
        "label": "Real Brasileiro",
        "exchange_label": "CME",
        "market_name": "BRAZILIAN REAL - CHICAGO MERCANTILE EXCHANGE",
        "yahoo_symbol": "BRL=F",
        "start_date": "2020-01-01",
    },
}


def _to_number(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return 0.0


def _to_int(value):
    return int(round(_to_number(value)))


def _to_iso_date(value):
    return str(value or "").strip()[:10]


def _parse_ymd(value):
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _to_unix_seconds(value):
    return int(_parse_ymd(value).timestamp())


def _add_days(value, days):
    base = _parse_ymd(value)
    shifted = datetime.fromtimestamp(base.timestamp() + days * 86400, tz=timezone.utc)
    return shifted.strftime("%Y-%m-%d")


def _read_url_text(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8-sig")


def fetch_cftc_rows(series_config):
    params = {
        "$select": ",".join(
            [
                "report_date_as_yyyy_mm_dd",
                "market_and_exchange_names",
                "noncomm_positions_long_all",
                "noncomm_positions_short_all",
                "comm_positions_short_all",
                "noncomm_postions_spread_all",
            ]
        ),
        "$where": (
            f"market_and_exchange_names='{series_config['market_name']}' "
            f"AND report_date_as_yyyy_mm_dd >= '{series_config['start_date']}'"
        ),
        "$order": "report_date_as_yyyy_mm_dd asc",
        "$limit": 2000,
        "$offset": 0,
    }
    url = f"https://publicreporting.cftc.gov/resource/jun7-fc8e.csv?{urllib.parse.urlencode(params)}"

    reader = csv.DictReader(io.StringIO(_read_url_text(url)))
    rows = []
    for record in reader:
        date = _to_iso_date(record.get("report_date_as_yyyy_mm_dd"))
        if not date:
            continue
        non_comm_long = _to_int(record.get("noncomm_positions_long_all"))
        non_comm_short = _to_int(record.get("noncomm_positions_short_all"))
        spreading = _to_int(record.get("noncomm_postions_spread_all"))
        rows.append(
            {
                "date": date,
                "market": record.get("market_and_exchange_names", ""),
                "nonCommLong": non_comm_long,
                "nonCommShort": non_comm_short,
                "spreading": spreading,
                "net": non_comm_long - non_comm_short,
            }
        )

    return sorted(rows, key=lambda item: item["date"])


def fetch_yahoo_history(symbol, start_date, end_date):
    period1 = _to_unix_seconds(start_date)
    period2 = _to_unix_seconds(_add_days(end_date, 1))
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
        f"?period1={period1}&period2={period2}&interval=1d&includePrePost=false&events=history"
    )
    data = json.loads(_read_url_text(url))
    result = ((data.get("chart") or {}).get("result") or [None])[0] or {}
    timestamps = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0] or {}).get("close") or []

    rows = []
    for index, timestamp in enumerate(timestamps):
        close_value = closes[index] if index < len(closes) else None
        close_number = _to_number(close_value)
        if close_number <= 0:
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(int(timestamp), tz=timezone.utc).strftime("%Y-%m-%d"),
                "soyClose": close_number,
            }
        )

    return sorted(rows, key=lambda item: item["date"])


def merge_price_into_positions(position_rows, price_rows):
    merged = []
    price_index = 0
    last_close = None

    for row in position_rows:
        while price_index < len(price_rows) and price_rows[price_index]["date"] <= row["date"]:
            last_close = price_rows[price_index]["soyClose"]
            price_index += 1
        merged.append({**row, "soyClose": last_close})

    return merged


def build_fund_position_payload(series_id="soja"):
    series_key = str(series_id or "soja").strip().lower()
    series_config = FUND_POSITION_SERIES.get(series_key)
    if not series_config:
        raise ValueError("Serie informada nao e suportada.")

    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cftc_rows = fetch_cftc_rows(series_config)
    if not cftc_rows:
        raise RuntimeError("Nenhum dado retornou do endpoint CFTC.")

    yahoo_rows = fetch_yahoo_history(
        series_config["yahoo_symbol"],
        series_config["start_date"],
        end_date,
    )
    if not yahoo_rows:
        raise RuntimeError("Nenhum dado retornou do Yahoo Finance.")

    rows = merge_price_into_positions(cftc_rows, yahoo_rows)
    latest = rows[-1]

    return {
        "availableSeries": [
            {
                "id": item["id"],
                "label": item["label"],
                "exchangeLabel": item["exchange_label"],
            }
            for item in FUND_POSITION_SERIES.values()
        ],
        "series": {
            "id": series_config["id"],
            "label": series_config["label"],
            "exchangeLabel": series_config["exchange_label"],
            "marketName": series_config["market_name"],
            "symbol": series_config["yahoo_symbol"],
        },
        "startDate": series_config["start_date"],
        "endDate": end_date,
        "rows": rows,
        "latest": {
            "date": latest["date"],
            "net": latest["net"],
            "nonCommLong": latest["nonCommLong"],
            "nonCommShort": latest["nonCommShort"],
            "spreading": latest["spreading"],
            "soyClose": latest["soyClose"],
        },
    }
