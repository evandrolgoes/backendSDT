"""Avaliação server-side de gatilhos atingidos + e-mail aos subgrupos.

Roda no servidor (dentro do loop de 60s do tradingview_scraper, ou via o
management command `evaluate_trigger_alerts`), independente de haver navegador
aberto. Compara o preço atual de cada gatilho derivativo (cotação já coletada
em `TradingViewWatchlistQuote`) contra o strike/direção e, na *virada* para
atingido, envia e-mail ao dono e aos usuários com acesso dos subgrupos do
gatilho e marca o status como "Atingido".

A lógica de match/hit é portada de `findMatchingDerivativeQuote` /
`evaluatedTriggers` do front (DashboardPage.jsx) para manter paridade.
"""

import logging
import unicodedata

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.tradingview_scraper.models import TradingViewWatchlistQuote

from .models import StrategyTrigger, TriggerAlertLog

logger = logging.getLogger(__name__)


# ── Helpers portados do front ────────────────────────────────────────────────

def normalize_text(value):
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.strip().lower()


def normalize_lookup_key(value):
    return "".join(ch for ch in normalize_text(value) if ch.isalnum())


def _first_nonblank(*values):
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def resolve_contract(trigger):
    return _first_nonblank(
        trigger.contrato_derivativo, trigger.contrato_bolsa, trigger.codigo_derivativo
    )


def resolve_exchange(trigger):
    return _first_nonblank(trigger.bolsa, trigger.produto_bolsa)


def resolve_direction(trigger):
    return _first_nonblank(trigger.acima_abaixo)


def resolve_type(trigger):
    return _first_nonblank(trigger.tipo, trigger.tipo_fis_der)


def resolve_strike(trigger):
    value = trigger.strike if trigger.strike is not None else trigger.strike_alvo
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def find_matching_quote(trigger, quotes):
    """Espelha findMatchingDerivativeQuote (exato por ticker, depois fuzzy)."""
    contract_key = normalize_lookup_key(resolve_contract(trigger))
    if not contract_key:
        return None

    exchange_key = normalize_lookup_key(resolve_exchange(trigger))

    for quote in quotes:
        ticker_key = normalize_lookup_key(quote.ticker or quote.symbol)
        if ticker_key != contract_key:
            continue
        if not exchange_key:
            return quote
        section_key = normalize_lookup_key(quote.section_name)
        description_key = normalize_lookup_key(quote.description)
        if exchange_key in section_key or exchange_key in description_key:
            return quote

    for quote in quotes:
        candidates = [
            normalize_lookup_key(quote.ticker),
            normalize_lookup_key(quote.symbol),
            normalize_lookup_key(quote.description),
            normalize_lookup_key(quote.section_name),
        ]
        matches_contract = any(
            c and (contract_key in c or c in contract_key) for c in candidates
        )
        if not matches_contract:
            continue
        if not exchange_key:
            return quote
        if any(c and exchange_key in c for c in candidates):
            return quote

    return None


def is_hit(trigger, quote):
    """Retorna (hit: bool, price: float|None). Só vale para derivativo."""
    if normalize_text(resolve_type(trigger)) != "derivativo":
        return False, None
    if quote is None or quote.price is None:
        return False, None
    try:
        price = float(quote.price)
    except (TypeError, ValueError):
        return False, None
    strike = resolve_strike(trigger)
    if strike <= 0:
        return False, price
    if "abaixo" in normalize_text(resolve_direction(trigger)):
        return price <= strike, price
    return price >= strike, price


# ── Destinatários ────────────────────────────────────────────────────────────

def resolve_recipients(trigger):
    """Dono + usuários com acesso dos subgrupos do gatilho.

    Apenas usuários ativos, com e-mail, fora de tenants de teste. Sem
    subgrupo => sem destinatários (decisão do produto).
    """
    users = {}
    for subgroup in trigger.subgrupos.all():
        candidates = list(subgroup.users_with_access.all())
        if subgroup.owner_id:
            candidates.append(subgroup.owner)
        for user in candidates:
            if user is None or not user.is_active:
                continue
            email = (user.email or "").strip()
            if not email:
                continue
            if user.tenant_id and getattr(user.tenant, "is_test", False):
                continue
            users[user.id] = email
    return sorted(set(users.values()))


# ── E-mail ───────────────────────────────────────────────────────────────────

def _format_number(value):
    if value is None:
        return "—"
    try:
        return f"{float(value):,.4f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(value)


def build_email(trigger, price):
    contract = resolve_contract(trigger) or f"Gatilho {trigger.id}"
    direction = resolve_direction(trigger) or "—"
    exchange = resolve_exchange(trigger) or "—"
    strike = _format_number(resolve_strike(trigger))
    estrategia = ""
    if trigger.estrategia_id:
        estrategia = (trigger.estrategia.descricao_estrategia or f"Estratégia {trigger.estrategia_id}").strip()
    subgrupos = ", ".join(
        s.subgrupo for s in trigger.subgrupos.all() if s.subgrupo
    ) or "—"
    quando = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")

    subject = f"🔔 Gatilho atingido: {contract} {direction} {strike}"
    body = (
        f"O gatilho abaixo foi ATINGIDO em {quando}.\n\n"
        f"Contrato: {contract}\n"
        f"Bolsa: {exchange}\n"
        f"Regra: {direction} de {strike}\n"
        f"Preço no momento: {_format_number(price)}\n"
        f"Estratégia: {estrategia or '—'}\n"
        f"Subgrupo(s): {subgrupos}\n\n"
        f"Este é um aviso automático do HedgePosition. Não responda este e-mail."
    )
    return subject, body


def _send(recipients, subject, body):
    """Envia individualmente (sem expor um cliente ao outro). Best-effort."""
    sent = 0
    for email in recipients:
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            sent += 1
        except Exception:  # noqa: BLE001 — um e-mail ruim não pode travar o resto
            logger.exception("Falha ao enviar alerta de gatilho para %s", email)
    return sent


# ── Avaliação principal ──────────────────────────────────────────────────────

def evaluate_trigger_alerts():
    """Avalia todos os gatilhos derivativos e dispara alertas na virada.

    Retorna um dict com contadores (útil para o management command/logs).
    """
    quotes = list(
        TradingViewWatchlistQuote.objects.exclude(price__isnull=True).only(
            "symbol", "ticker", "description", "section_name", "price"
        )
    )

    triggers = (
        StrategyTrigger.objects.filter(tenant__isnull=False)
        .exclude(tenant__is_test=True)
        .prefetch_related("subgrupos", "subgrupos__users_with_access", "subgrupos__owner")
        .select_related("estrategia", "tenant")
    )

    stats = {"evaluated": 0, "hits": 0, "alerts": 0, "emails": 0, "rearmed": 0}

    for trigger in triggers:
        if normalize_text(resolve_type(trigger)) != "derivativo":
            continue
        if normalize_text(trigger.status) == "inativo":
            continue
        stats["evaluated"] += 1

        quote = find_matching_quote(trigger, quotes)
        hit, price = is_hit(trigger, quote)

        if hit:
            stats["hits"] += 1
            if trigger.alert_state == StrategyTrigger.ALERT_STATE_ARMED:
                _handle_hit(trigger, price, stats)
        else:
            if trigger.alert_state == StrategyTrigger.ALERT_STATE_ALERTED:
                trigger.alert_state = StrategyTrigger.ALERT_STATE_ARMED
                trigger.save(update_fields=["alert_state"])
                stats["rearmed"] += 1

    return stats


def _handle_hit(trigger, price, stats):
    """Virada armed -> atingido: e-mail, status='Atingido', log, dedupe."""
    recipients = resolve_recipients(trigger)
    subject, body = build_email(trigger, price)

    sent = _send(recipients, subject, body) if recipients else 0

    with transaction.atomic():
        trigger.alert_state = StrategyTrigger.ALERT_STATE_ALERTED
        trigger.alerted_at = timezone.now()
        trigger.alert_price = price
        trigger.status = "Atingido"
        trigger.status_gatilho = "Atingido"
        trigger.save(
            update_fields=[
                "alert_state",
                "alerted_at",
                "alert_price",
                "status",
                "status_gatilho",
            ]
        )
        TriggerAlertLog.objects.create(
            trigger=trigger,
            contract=resolve_contract(trigger)[:120],
            direction=resolve_direction(trigger)[:20],
            strike=resolve_strike(trigger) or None,
            price=price,
            recipients=recipients,
            email_sent=sent > 0,
            detail="" if recipients else "Sem destinatários (gatilho sem subgrupo).",
        )

    stats["alerts"] += 1
    stats["emails"] += sent
