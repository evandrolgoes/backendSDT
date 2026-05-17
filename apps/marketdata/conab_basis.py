"""Construção do dataset sazonal de basis (CONAB + CBOT + PTAX).

Fonte primária: cubo Mondrian `Preco_Produto_Municipio_10_Anos` da CONAB,
acessado via XMLA (mesmo endpoint que o portal usa). Esse cubo é a série
semanal por município de preço recebido pelo produtor (R$/sc 60kg). Quando a
CONAB carrega novas semanas (inclusive a virada de ano), elas aparecem aqui
automaticamente — basta o coletor rodar de novo.

Referência de bolsa: CBOT (Soja ZS=F, Milho ZC=F) via Yahoo, normalizado /100
(cents → US$/bushel, igual a `services._normalize_price_for_ticker`).
Dólar: PTAX de venda (fechamento) do Banco Central (API Olinda), em lote.

O payload tem exatamente o formato consumido pelo front (Basis2Page):
{meta, cultures, cities, byCulture, refDaily, ptaxDaily}.
"""

import html
import json
import re
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

XMLA_URL = (
    "https://pentahoportaldeinformacoes.conab.gov.br/pentaho/Xmla"
    "?userid=pentaho&password=password"
)
CUBE = "Preco_Produto_Municipio_10_Anos"
HISTORY_START_YEAR = 2013

# Conjunto curado de praças (precisa existir no cubo p/ a cultura). A
# interseção com os membros NON EMPTY evita erro de membro inexistente.
CURATED_CITIES = [
    "BAIXA GRANDE DO RIBEIRO-PI", "BALSAS-MA", "BARREIRAS-BA",
    "CAMPO NOVO DO PARECIS-MT", "CASCAVEL-PR", "CHAPECÓ-SC", "CRISTALINA-GO",
    "DOURADOS-MS", "GUARAPUAVA-PR", "JATAÍ-GO", "LONDRINA-PR",
    "LUCAS DO RIO VERDE-MT", "MARACAJU-MS", "NOVA MUTUM-MT", "PASSO FUNDO-RS",
    "PONTA GROSSA-PR", "RIO VERDE-GO", "RONDONÓPOLIS-MT", "SORRISO-MT",
    "UBERLÂNDIA-MG",
]

# Cultura → bolsa(s) de referência. fator = sc 60kg → bushel
# (soja: 60/27,2155 ; milho: 60/25,4012). Mesma conta de compute_sale_basis.
CULTURES = [
    {
        "key": "SOJA", "label": "Soja", "unidadeBasis": "US$/bushel",
        "dolar": "PTAX BCB (venda, fechamento)",
        "references": [
            {"key": "soja_cbot", "label": "Soja CBOT", "fator": 2.2046,
             "unidade": "US$/bushel", "yahoo": "ZS=F"},
        ],
    },
    {
        "key": "MILHO", "label": "Milho", "unidadeBasis": "US$/bushel",
        "dolar": "PTAX BCB (venda, fechamento)",
        "references": [
            {"key": "milho_cbot", "label": "Milho CBOT", "fator": 2.3621,
             "unidade": "US$/bushel", "yahoo": "ZC=F"},
        ],
    },
]

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _xmla(mdx, tries=4):
    envelope = (
        '<?xml version="1.0"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
        '<Execute xmlns="urn:schemas-microsoft-com:xml-analysis">'
        f"<Command><Statement>{html.escape(mdx)}</Statement></Command>"
        "<Properties><PropertyList>"
        "<DataSourceInfo>Provider=Mondrian</DataSourceInfo>"
        "<Catalog>Preco_Medio</Catalog><Format>Multidimensional</Format>"
        "<AxisFormat>TupleFormat</AxisFormat>"
        "</PropertyList></Properties></Execute></soap:Body></soap:Envelope>"
    )
    headers = {
        "Content-Type": "text/xml; charset=UTF-8",
        "SOAPAction": '"urn:schemas-microsoft-com:xml-analysis:Execute"',
    }
    last_error = None
    for attempt in range(tries):
        try:
            request = Request(XMLA_URL, data=envelope.encode("utf-8"), headers=headers)
            with urlopen(request, timeout=240) as response:
                return response.read().decode("utf-8")
        except Exception as exc:  # rede instável da CONAB: retry com backoff
            last_error = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"XMLA falhou após {tries} tentativas: {last_error}")


def _axis(xml, name):
    match = re.search(rf'<Axis name="{name}">(.*?)</Axis>', xml, re.S)
    return match.group(1) if match else ""


def _members(prod):
    mdx = (
        "SELECT {[Measures].[Preco Medio Comercializado]} ON COLUMNS, "
        "NON EMPTY [Municipio].[Municipio].Members ON ROWS "
        f"FROM [{CUBE}] WHERE ([Produto].[{prod}],[Classificacao].[EM GRÃOS],"
        "[Nivel Comercializacao].[PREÇO RECEBIDO P/ PRODUTOR],[Tipo Visao].[SEMANAL])"
    )
    axis = _axis(_xmla(mdx), "Axis1")
    return set(re.findall(r"<Member[^>]*>.*?<Caption>(.*?)</Caption>", axis, re.S))


def _fetch_culture(prod, cities):
    """{cidade: [{date, price}]} para a cultura, ordenado por data."""
    if not cities:
        return {}
    members = ",".join(f"[Municipio].[{c}]" for c in cities)
    mdx = (
        f"SELECT NON EMPTY CrossJoin({{{members}}}, "
        "{[Measures].[Preco Medio Comercializado]}) ON COLUMNS, "
        f"NON EMPTY [Semana].[Data Inicial Final].Members ON ROWS FROM [{CUBE}] "
        f"WHERE ([Produto].[{prod}],[Classificacao].[EM GRÃOS],"
        "[Nivel Comercializacao].[PREÇO RECEBIDO P/ PRODUTOR],[Tipo Visao].[SEMANAL])"
    )
    xml = _xmla(mdx)
    cols = re.findall(r"<Caption>(.*?)</Caption>", _axis(xml, "Axis0"))
    col_cities = [cols[i] for i in range(0, len(cols), 2)]  # (municipio, measure)
    ncol = len(col_cities)
    weeks = re.findall(
        r"<Member[^>]*>.*?<Caption>(.*?)</Caption>", _axis(xml, "Axis1"), re.S
    )
    cells = {}
    for cell in re.finditer(
        r'<Cell CellOrdinal="(\d+)">.*?<Value[^>]*>(.*?)</Value>', xml, re.S
    ):
        cells[int(cell.group(1))] = cell.group(2)
    out = {c: [] for c in col_cities}
    for row, week in enumerate(weeks):
        day, month, year = week.split(" - ")[0].strip().split("-")
        iso = f"{year}-{month}-{day}"
        for ci, city in enumerate(col_cities):
            value = cells.get(row * ncol + ci)
            if value not in (None, ""):
                out[city].append({"date": iso, "price": round(float(value), 2)})
    for city in out:
        out[city].sort(key=lambda r: r["date"])
    return {c: out[c] for c in cities if out.get(c)}


def _fetch_cbot_daily(yahoo_symbol):
    """Fechamento diário do contínuo CBOT em US$/bushel (cents/100)."""
    start = int(datetime(HISTORY_START_YEAR, 1, 1, tzinfo=timezone.utc).timestamp())
    end = int(datetime.now(timezone.utc).timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        f"?period1={start}&period2={end}&interval=1d"
    )
    with urlopen(Request(url, headers=_UA), timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    result = data["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    out = {}
    for ts, close in zip(result["timestamp"], closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
        out[day] = round(close / 100.0, 4)
    return out


def _fetch_ptax_daily():
    """PTAX USD/BRL (cotação de venda) por dia, via API Olinda do BCB.

    O Olinda é instável (503 frequente): tenta cada ano até 4x com backoff.
    O guard de completude em build_conab_basis_payload aborta o snapshot se
    o PTAX vier vazio/curto demais — assim uma queda do BCB não substitui um
    snapshot bom por um quebrado.
    """
    out = {}
    for year in range(HISTORY_START_YEAR, datetime.now(timezone.utc).year + 1):
        url = (
            "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
            "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)?"
            f"@dataInicial='01-01-{year}'&@dataFinalCotacao='12-31-{year}'"
            "&$format=json&$select=cotacaoVenda,dataHoraCotacao"
        )
        for attempt in range(4):
            try:
                with urlopen(Request(url, headers={**_UA, "Accept": "application/json"}), timeout=40) as response:
                    data = json.loads(response.read().decode("utf-8"))
                for row in data.get("value", []):
                    day = row["dataHoraCotacao"][:10]
                    out[day] = round(float(row["cotacaoVenda"]), 4)
                break
            except Exception:
                if attempt < 3:
                    time.sleep(3 * (attempt + 1))
    return out


def build_conab_basis_payload():
    """Monta o dataset completo. Lança em caso de falha dura (sem dados CONAB)."""
    soja_members = _members("SOJA")
    milho_members = _members("MILHO")

    by_culture = {}
    cities = set()
    for culture in CULTURES:
        prod = culture["key"]
        valid = milho_members if prod == "MILHO" else soja_members
        wanted = [c for c in CURATED_CITIES if c in valid]
        series = _fetch_culture(prod, wanted)
        by_culture[prod] = series
        cities.update(series.keys())

    if not cities:
        raise RuntimeError("CONAB não retornou nenhuma série — abortando snapshot.")

    ref_daily = {}
    for culture in CULTURES:
        for ref in culture["references"]:
            ref_daily[ref["key"]] = _fetch_cbot_daily(ref["yahoo"])

    ptax_daily = _fetch_ptax_daily()

    # Guard de completude: sem PTAX/CBOT íntegros o basis fica sem chão. Aborta
    # antes de gravar — o endpoint segue servindo o último snapshot bom (ou 204
    # → front cai no embutido). Evita que uma queda de BCB/Yahoo quebre o painel.
    if len(ptax_daily) < 200:
        raise RuntimeError(
            f"PTAX incompleto ({len(ptax_daily)} dias) — provável queda do BCB. "
            "Snapshot abortado; mantém o anterior."
        )
    for key, series in ref_daily.items():
        if len(series) < 200:
            raise RuntimeError(
                f"Cotação de referência '{key}' incompleta ({len(series)} dias). "
                "Snapshot abortado; mantém o anterior."
            )

    # Remove 'yahoo' do payload público (detalhe de coleta).
    cultures_public = [
        {
            **{k: v for k, v in c.items() if k != "references"},
            "references": [
                {k: v for k, v in r.items() if k != "yahoo"}
                for r in c["references"]
            ],
        }
        for c in CULTURES
    ]

    return {
        "meta": {
            "source": "CONAB SIAGRO (XMLA, Preco_Produto_Municipio_10_Anos)",
            "nivelComercializacao": "PREÇO RECEBIDO P/ PRODUTOR",
            "classificacao": "EM GRÃOS",
            "unidade": "R$/sc 60kg",
            "periodicidade": "semanal",
            "atualizadoEm": datetime.now(timezone.utc).isoformat(),
        },
        "cultures": cultures_public,
        "cities": sorted(cities),
        "byCulture": by_culture,
        "refDaily": ref_daily,
        "ptaxDaily": ptax_daily,
    }


def _last_week(payload):
    last = ""
    for series in payload.get("byCulture", {}).values():
        for rows in series.values():
            if rows and rows[-1]["date"] > last:
                last = rows[-1]["date"]
    return last


def collect_and_store():
    """Roda o build e grava um novo ConabBasisSnapshot. Retorna o snapshot."""
    from .models import ConabBasisSnapshot

    payload = build_conab_basis_payload()
    last_week = _last_week(payload)
    week_count = max(
        (len(rows) for series in payload["byCulture"].values() for rows in series.values()),
        default=0,
    )
    snapshot = ConabBasisSnapshot.objects.create(
        payload=payload, week_count=week_count, last_week=last_week
    )
    # Mantém só os 10 últimos snapshots (auditoria/rollback).
    stale_ids = list(
        ConabBasisSnapshot.objects.order_by("-updated_at").values_list("id", flat=True)[10:]
    )
    if stale_ids:
        ConabBasisSnapshot.objects.filter(id__in=stale_ids).delete()
    return snapshot
