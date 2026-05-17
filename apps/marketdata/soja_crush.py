"""Construção do dataset de esmagamento e cobertura das fábricas de soja.

Fonte primária: **USDA PSD Online** (Production, Supply & Distribution), bulk
CSV grátis e sem chave — `psd_oilseeds_csv.zip`. Série anual por ano-safra de
esmagamento (crush), importação, produção e estoques de soja, para China e
Brasil. Atualizado ~mensal junto do circular "Oilseeds: World Markets and
Trade". Quando o USDA carrega novo ano-safra, ele aparece aqui sozinho —
basta o coletor rodar de novo.

Capacidade instalada do Brasil: ABIOVE (página pública de "Capacidade
Instalada"). É raspagem defensiva — se a página mudar/cair, cai no último
valor conhecido (constantes validadas). A China não tem fonte pública
confiável de capacidade (só Mysteel/Cofeed, pagas), então a utilização da
China fica `null` e o front rotula isso explicitamente.

Limitação assumida: granularidade anual (ano-safra), não mensal. O payload
tem o formato consumido pelo front (SojaCoberturaPage):
{meta, countries:{BR,CN}, capacity, asOf}.
"""

import csv
import io
import re
import time
import zipfile
from datetime import datetime, timezone
from urllib.request import Request, urlopen

PSD_OILSEEDS_ZIP = "https://apps.fas.usda.gov/psdonline/downloads/psd_oilseeds_csv.zip"
ABIOVE_CAPACITY_URL = (
    "https://abiove.org.br/capacidade-instalada-da-industria-de-oleos-vegetais/"
)

SOYBEAN_COMMODITY_CODE = "2222000"  # "Oilseed, Soybean"
HISTORY_YEARS = 12

# Atributo do PSD → chave no payload. 1000 MT no CSV → convertido p/ Mt.
ATTRIBUTES = {
    "Production": "production",
    "Imports": "imports",
    "Crush": "crush",
    "Beginning Stocks": "beginning_stocks",
    "Ending Stocks": "ending_stocks",
    "Exports": "exports",
    "Domestic Consumption": "domestic_consumption",
}

COUNTRIES = {"Brazil": "BR", "China": "CN"}

# Capacidade instalada da indústria de soja (ABIOVE) — fallback validado em
# 16/mai/2026. Usado quando a raspagem falha. ~219.067 t/dia, 330 dias úteis.
ABIOVE_BAKED_CAPACITY = {
    "annual_mt": 72.3,
    "daily_t": 219067,
    "plants_active": 113,
    "plants_total": 132,
    "idle_pct": 24.6,
    "as_of": "2026",
    "source": "ABIOVE — Capacidade Instalada (valor de referência)",
}

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _download(url, tries=4, timeout=180):
    """GET binário com retry+backoff (USDA/ABIOVE caem com alguma frequência)."""
    last_error = None
    for attempt in range(tries):
        try:
            with urlopen(Request(url, headers=_UA), timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            last_error = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Download falhou após {tries} tentativas ({url}): {last_error}")


def _fetch_psd_rows():
    """Lê o CSV do zip do USDA em memória e devolve as linhas de soja.

    O CSV tem vírgula dentro de aspas (campos como "Oilseed, Soybean"), então
    parseia com csv.reader — nunca split por vírgula.
    """
    blob = _download(PSD_OILSEEDS_ZIP)
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(name) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
            header = next(reader)
            col = {name: i for i, name in enumerate(header)}
            for row in reader:
                if row[col["Commodity_Code"]] == SOYBEAN_COMMODITY_CODE:
                    yield row, col


def _build_countries():
    """{ 'BR': {2014: {crush, imports, ...}, ...}, 'CN': {...} } em Mt."""
    cutoff = datetime.now(timezone.utc).year - HISTORY_YEARS
    out = {code: {} for code in COUNTRIES.values()}
    for row, col in _fetch_psd_rows():
        country = row[col["Country_Name"]]
        code = COUNTRIES.get(country)
        if code is None:
            continue
        attr = row[col["Attribute_Description"]]
        key = ATTRIBUTES.get(attr)
        if key is None:
            continue
        try:
            year = int(row[col["Market_Year"]])
            value = float(row[col["Value"]])
        except (ValueError, TypeError):
            continue
        if year < cutoff:
            continue
        out[code].setdefault(year, {})[key] = round(value / 1000.0, 3)  # 1000 MT → Mt
    # Vira lista ordenada por ano: [{year, crush, imports, ...}].
    series = {}
    for code, by_year in out.items():
        series[code] = [
            {"year": year, **by_year[year]} for year in sorted(by_year)
        ]
    return series


def _num(text):
    """'219.067' / '72,3' → float (formato pt-BR: ponto = milhar, vírgula = decimal)."""
    cleaned = text.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


# Faixas de sanidade: a ABIOVE muda o texto da página de tempos em tempos e o
# regex pode casar um número de outra seção. Só sobrescreve o baked quando o
# valor raspado é plausível — senão mantém o último valor validado.
_CAPACITY_BOUNDS = {
    "daily_t": (100_000, 400_000),
    "annual_mt": (40, 120),
    "plants_active": (50, 250),
    "plants_total": (50, 300),
    "idle_pct": (0, 60),
}


def _fetch_abiove_capacity():
    """Raspa a capacidade instalada da ABIOVE. Cai no baked se algo falhar."""
    capacity = dict(ABIOVE_BAKED_CAPACITY)
    try:
        html = _download(ABIOVE_CAPACITY_URL, tries=3, timeout=40).decode(
            "utf-8", "ignore"
        )
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
    except Exception:
        return capacity

    scraped = {}
    m = re.search(r"([\d.]+)\s*toneladas?\s*por\s*dia", text, re.I)
    if m and _num(m.group(1)):
        scraped["daily_t"] = int(_num(m.group(1)))
    m = re.search(r"([\d,]+)\s*milh[õo]es?\s*de\s*toneladas", text, re.I)
    if m and _num(m.group(1)):
        scraped["annual_mt"] = _num(m.group(1))
    m = re.search(r"(\d+)\s*f[áa]bricas?\s*(?:em\s*opera|ativ)", text, re.I)
    if m:
        scraped["plants_active"] = int(m.group(1))
    m = re.search(r"(\d+)\s*unidades?\s*industriais", text, re.I)
    if m:
        scraped["plants_total"] = int(m.group(1))
    m = re.search(r"([\d,]+)\s*%[^.]{0,40}ociosidade", text, re.I) or re.search(
        r"ociosidade[^.]{0,40}?([\d,]+)\s*%", text, re.I
    )
    if m and _num(m.group(1)):
        scraped["idle_pct"] = _num(m.group(1))

    applied = False
    for key, value in scraped.items():
        low, high = _CAPACITY_BOUNDS[key]
        if low <= value <= high:
            capacity[key] = value
            applied = True
    # total < ativas é incoerente → descarta o total raspado.
    if capacity["plants_total"] < capacity["plants_active"]:
        capacity["plants_total"] = ABIOVE_BAKED_CAPACITY["plants_total"]
    capacity["source"] = (
        "ABIOVE — Capacidade Instalada (raspado)"
        if applied
        else "ABIOVE — Capacidade Instalada (valor de referência)"
    )
    return capacity


def build_soja_crush_payload():
    """Monta o dataset completo. Lança em falha dura (sem dados do USDA)."""
    countries = _build_countries()

    br = countries.get("BR") or []
    cn = countries.get("CN") or []
    if not any("crush" in row for row in br) or not any("crush" in row for row in cn):
        raise RuntimeError(
            "USDA PSD não retornou esmagamento de Brasil/China — abortando snapshot."
        )

    capacity = _fetch_abiove_capacity()

    # Utilização do Brasil = esmagamento do ano / capacidade instalada atual.
    # Só há capacidade pública corrente (não série histórica), então a linha de
    # capacidade é uma referência fixa e a utilização é "vs capacidade atual".
    cap_mt = capacity.get("annual_mt") or 0
    for row in br:
        if cap_mt and "crush" in row:
            row["utilization_pct"] = round(row["crush"] / cap_mt * 100, 1)

    latest_my = max((row["year"] for row in br + cn), default=0)

    return {
        "meta": {
            "crushSource": "USDA PSD Online (psd_oilseeds, Oilseed Soybean)",
            "capacitySource": capacity["source"],
            "unit": "milhões de toneladas (Mt)",
            "periodicidade": "anual (ano-safra)",
            "limitacoes": (
                "Série anual (não mensal). China não tem fonte pública de "
                "capacidade instalada — utilização da China não é calculada."
            ),
            "atualizadoEm": datetime.now(timezone.utc).isoformat(),
        },
        "countries": {
            "BR": {"label": "Brasil", "series": br},
            "CN": {"label": "China", "series": cn},
        },
        "capacity": {"BR": capacity, "CN": None},
        "latestMarketYear": latest_my,
    }


def collect_and_store():
    """Roda o build e grava um novo SojaCrushSnapshot. Retorna o snapshot."""
    from .models import SojaCrushSnapshot

    payload = build_soja_crush_payload()
    snapshot = SojaCrushSnapshot.objects.create(
        payload=payload,
        latest_market_year=payload["latestMarketYear"],
        source_note=payload["meta"]["crushSource"][:200],
    )
    # Mantém só os 10 últimos snapshots (auditoria/rollback).
    stale_ids = list(
        SojaCrushSnapshot.objects.order_by("-updated_at").values_list("id", flat=True)[
            10:
        ]
    )
    if stale_ids:
        SojaCrushSnapshot.objects.filter(id__in=stale_ids).delete()
    return snapshot
