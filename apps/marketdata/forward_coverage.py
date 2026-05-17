"""Cobertura forward das fábricas de soja (compra antecipada, olhando à frente).

Provider-agnóstico e honesto: cada provedor só produz série se tiver
credencial configurada. Sem credencial → status "not_configured" e o
dashboard mostra um placeholder pedindo pra conectar. **Nunca inventa dado.**

- Brasil → SAFRAS Data Feed: % da necessidade de esmagamento já comprada,
  por mês à frente ("cobertura das fábricas" / comercialização). É o número
  exato. API/feed contratado (env `SAFRAS_DATAFEED_URL`/`SAFRAS_DATAFEED_TOKEN`).
- China → Kpler Grains & Oilseeds Flows: soja já embarcada / em line-up
  forward com ETA na China, por mês — proxy automatizável de "quanto já foi
  comprado, daqui pra frente" (env `KPLER_API_URL`/`KPLER_API_TOKEN`).

⚠️ SEAM DE INTEGRAÇÃO: o schema exato de SAFRAS/Kpler depende do contrato.
As funções `_normalize_safras` / `_normalize_kpler` são o único ponto a
ajustar quando você tiver um sample real do feed — o resto (HTTP, auth,
snapshot, dashboard) já fica pronto e estável.
"""

import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

FORWARD_MONTHS = 12  # janela à frente exibida no dashboard

_UA = {"User-Agent": "HedgePosition/1.0 (forward-coverage collector)"}


def _forward_window(n=FORWARD_MONTHS):
    """['2026-06', '2026-07', ...] — n meses a partir do mês corrente."""
    now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    out = []
    for _ in range(n):
        out.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return out


def _get_json(url, token=None, params=None, timeout=40, auth_header="Bearer"):
    """GET autenticado → JSON. Lança em erro de rede/HTTP (o caller trata)."""
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urlencode(params)}"
    headers = {**_UA, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"{auth_header} {token}"
    with urlopen(Request(url, headers=headers), timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _provider_result(name, status, *, unit="", points=None, message=""):
    return {
        "provider": name,
        "status": status,  # ok | not_configured | error | empty
        "unit": unit,
        "message": message,
        "points": points or [],  # [{"month": "2026-06", "value": 62.5}]
    }


# --------------------------------------------------------------------------
# Brasil — SAFRAS Data Feed (% da necessidade já comprada, por mês à frente)
# --------------------------------------------------------------------------

def _normalize_safras(raw):
    """SEAM: mapeia o payload do SAFRAS Data Feed → [{month, value}].

    `value` = % da necessidade de esmagamento já comprada para o mês.
    Aceita já um formato canônico simples — AJUSTAR aqui quando tiver o
    sample real do contrato (nome dos campos, unidade, mês AAAA-MM).
    """
    rows = raw.get("data") if isinstance(raw, dict) else raw
    points = []
    for row in rows or []:
        month = row.get("month") or row.get("mes") or row.get("referencia")
        value = row.get("coverage") or row.get("cobertura") or row.get("value")
        if month and value is not None:
            points.append({"month": str(month)[:7], "value": round(float(value), 1)})
    points.sort(key=lambda p: p["month"])
    return points


def _collect_safras():
    url = getattr(settings, "SAFRAS_DATAFEED_URL", "")
    token = getattr(settings, "SAFRAS_DATAFEED_TOKEN", "")
    name = "SAFRAS Data Feed (cobertura das fábricas — Brasil)"
    if not url:
        return _provider_result(
            name, "not_configured", unit="% da necessidade",
            message="Defina SAFRAS_DATAFEED_URL/SAFRAS_DATAFEED_TOKEN para ativar.",
        )
    try:
        raw = _get_json(url, token=token, params={"produto": "soja"})
        points = _normalize_safras(raw)
        if not points:
            return _provider_result(
                name, "empty", unit="% da necessidade",
                message="Feed respondeu sem cobertura — revisar mapeamento (_normalize_safras).",
            )
        return _provider_result(name, "ok", unit="% da necessidade", points=points)
    except (HTTPError, URLError, ValueError, KeyError) as exc:
        return _provider_result(
            name, "error", unit="% da necessidade",
            message=f"Falha ao consultar SAFRAS: {exc}",
        )


# --------------------------------------------------------------------------
# China — Kpler Grains & Oilseeds Flows (soja embarcada forward p/ China)
# --------------------------------------------------------------------------

def _normalize_kpler(raw):
    """SEAM: mapeia o payload do Kpler Flows → [{month, value}] em Mt.

    `value` = soja com ETA no mês na China (line-up forward) — proxy de
    compra já comprometida. AJUSTAR ao schema real do Kpler na credencial
    (endpoint `/v1/flows`, agrupamento mensal, unidade em t → /1e6 = Mt).
    """
    series = raw.get("series") or raw.get("data") if isinstance(raw, dict) else raw
    points = []
    for row in series or []:
        month = row.get("date") or row.get("month")
        value = row.get("value") or row.get("volume")
        if month and value is not None:
            mt = float(value)
            if mt > 1000:  # veio em toneladas → Mt
                mt = mt / 1_000_000
            points.append({"month": str(month)[:7], "value": round(mt, 3)})
    points.sort(key=lambda p: p["month"])
    return points


def _collect_kpler():
    url = getattr(settings, "KPLER_API_URL", "")
    token = getattr(settings, "KPLER_API_TOKEN", "")
    name = "Kpler Grains & Oilseeds Flows (line-up forward — China)"
    if not url or not token:
        return _provider_result(
            name, "not_configured", unit="Mt (embarque forward p/ China)",
            message="Defina KPLER_API_TOKEN para ativar (Kpler via API/ICE).",
        )
    try:
        raw = _get_json(
            f"{url.rstrip('/')}/v1/flows",
            token=token,
            params={
                "product": "soybeans",
                "toZone": "China",
                "flowDirection": "import",
                "granularity": "months",
                "split": "eta",
            },
        )
        points = _normalize_kpler(raw)
        if not points:
            return _provider_result(
                name, "empty", unit="Mt (embarque forward p/ China)",
                message="Kpler respondeu sem fluxo — revisar mapeamento (_normalize_kpler).",
            )
        return _provider_result(
            name, "ok", unit="Mt (embarque forward p/ China)", points=points
        )
    except (HTTPError, URLError, ValueError, KeyError) as exc:
        return _provider_result(
            name, "error", unit="Mt (embarque forward p/ China)",
            message=f"Falha ao consultar Kpler: {exc}",
        )


# --------------------------------------------------------------------------

def build_forward_coverage_payload():
    """Monta o dataset. Sempre retorna (mesmo tudo 'não configurado') — o
    estado dos provedores É a informação que o dashboard precisa mostrar."""
    br = _collect_safras()
    cn = _collect_kpler()
    months = _forward_window()
    statuses = f"BR={br['status']} · CN={cn['status']}"
    return {
        "meta": {
            "title": "Cobertura forward das fábricas (apetite de compra)",
            "description": (
                "Brasil: % da necessidade de esmagamento já comprada por mês "
                "(SAFRAS). China: soja embarcada/line-up forward com ETA no "
                "mês (Kpler) — proxy de compra comprometida."
            ),
            "forwardOnly": True,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "statuses": statuses,
        },
        "months": months,
        "series": {"BR": br, "CN": cn},
    }


def collect_and_store():
    """Roda o build e grava um novo ForwardCoverageSnapshot."""
    from .models import ForwardCoverageSnapshot

    payload = build_forward_coverage_payload()
    snapshot = ForwardCoverageSnapshot.objects.create(
        payload=payload,
        providers_note=payload["meta"]["statuses"][:200],
    )
    stale_ids = list(
        ForwardCoverageSnapshot.objects.order_by("-updated_at").values_list(
            "id", flat=True
        )[10:]
    )
    if stale_ids:
        ForwardCoverageSnapshot.objects.filter(id__in=stale_ids).delete()
    return snapshot
