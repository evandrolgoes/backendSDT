import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from http.cookiejar import CookieJar

from django.conf import settings
from django.utils import timezone


DEFAULT_MARKET_SUMMARY_OBJECTIVE = (
    "Gerar um resumo semanal de mercado para produtores rurais, com leitura executiva, "
    "tom profissional, prudente e foco em decisao comercial."
)

DEFAULT_MARKET_SUMMARY_OUTLINE = """Principais Acontecimentos da Semana

Performance das Commodities

Macroeconomia
Macroeconomia - Brasil
Macroeconomia - Guerras

Dolar

Mercado da Soja
Premios Paranagua
Evolucao da Safra
Analise Grafica da Soja CBOT

Mercado do Milho

Insumos

Clima - Destaques da Semana

Agenda da Semana

Posicao de Fundos

Estrategias Recomendadas para Produtores Rurais

Demais Numeros da Soja

Demais Numeros do Milho"""

DEFAULT_MARKET_SUMMARY_SOURCES = [
    {"title": "Noticias Agricolas", "url": "https://www.noticiasagricolas.com.br/noticias/", "content": ""},
    {"title": "InfoMoney Economia", "url": "https://www.infomoney.com.br/economia/", "content": ""},
]

BULLET_SECTION_TITLES = {
    "principais acontecimentos da semana",
    "performance das commodities",
    "agenda da semana",
    "posicao de fundos",
    "estrategias recomendadas para produtores rurais",
    "demais numeros da soja",
    "demais numeros do milho",
}

AUTO_SOURCE_LIMIT = 4
AUTO_SOURCE_TEXT_LIMIT = 5000


def _normalize_source(item, index):
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "").strip()
    content = str(item.get("content") or "").strip()

    if not title and not url and not content:
        return None

    return {
        "index": index + 1,
        "title": title or f"Fonte {index + 1}",
        "url": url,
        "content": content,
    }


def _strip_tags(value):
    no_scripts = re.sub(r"<script.*?</script>", "", value or "", flags=re.IGNORECASE | re.DOTALL)
    no_styles = re.sub(r"<style.*?</style>", "", no_scripts, flags=re.IGNORECASE | re.DOTALL)
    plain = re.sub(r"<[^>]+>", " ", no_styles)
    return re.sub(r"\s+", " ", html.unescape(plain)).strip()


def _html_to_text(value):
    normalized = value or ""
    normalized = re.sub(r"<br\s*/?>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</p\s*>", "\n\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</div\s*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<hr\s*/?>", "\n\n---\n\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<li[^>]*>", "- ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</li\s*>", "\n", normalized, flags=re.IGNORECASE)
    no_scripts = re.sub(r"<script.*?</script>", "", normalized, flags=re.IGNORECASE | re.DOTALL)
    no_styles = re.sub(r"<style.*?</style>", "", no_scripts, flags=re.IGNORECASE | re.DOTALL)
    plain = re.sub(r"<[^>]+>", " ", no_styles)
    plain = html.unescape(plain)
    plain = re.sub(r"\r", "", plain)
    plain = re.sub(r"[ \t]+\n", "\n", plain)
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    plain = re.sub(r"[ \t]{2,}", " ", plain)
    return plain.strip()


def _fetch_text(url, *, headers=None, data=None, method=None):
    request = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "Mozilla/5.0", **(headers or {})},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _extract_meta_content(page_html, key):
    patterns = [
        rf'<meta[^>]+property="{re.escape(key)}"[^>]+content="([^"]+)"',
        rf'<meta[^>]+content="([^"]+)"[^>]+property="{re.escape(key)}"',
        rf'<meta[^>]+name="{re.escape(key)}"[^>]+content="([^"]+)"',
        rf'<meta[^>]+content="([^"]+)"[^>]+name="{re.escape(key)}"',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def _extract_article_text(page_html):
    article_match = re.search(r"<article\b.*?</article>", page_html, flags=re.IGNORECASE | re.DOTALL)
    scope = article_match.group(0) if article_match else page_html
    paragraphs = []
    for paragraph in re.findall(r"<p\b[^>]*>(.*?)</p>", scope, flags=re.IGNORECASE | re.DOTALL):
        text = _html_to_text(paragraph)
        if len(text) < 40:
            continue
        if text not in paragraphs:
            paragraphs.append(text)
        if len(paragraphs) >= 12:
            break
    return "\n\n".join(paragraphs)[:AUTO_SOURCE_TEXT_LIMIT]


def _extract_article_date(page_html):
    for pattern in [
        r'<time[^>]+datetime="([^"]+)"',
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"uploadDate"\s*:\s*"([^"]+)"',
    ]:
        match = re.search(pattern, page_html, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    date_match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", page_html)
    return date_match.group(1) if date_match else ""


def _parse_recent_cutoff(days=7):
    return timezone.now() - timedelta(days=days)


def _parse_article_date(value):
    parsed_value = str(value or "").strip()
    if not parsed_value:
        return None

    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            parsed = datetime.strptime(parsed_value, fmt)
        except ValueError:
            continue
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    normalized = parsed_value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _normalize_link(base_url, href):
    candidate = str(href or "").strip()
    if not candidate or candidate.startswith("#") or candidate.startswith("javascript:"):
        return ""
    return urllib.parse.urljoin(base_url, candidate)


def _is_agrinvest_source(source):
    target = " ".join([source.get("title") or "", source.get("url") or ""]).lower()
    return "agrinvest" in target or "go.agrinvest.agr.br/noticias" in target


def _is_noticias_agricolas_source(source):
    target = " ".join([source.get("title") or "", source.get("url") or ""]).lower()
    return "noticiasagricolas.com.br" in target


def _is_infomoney_source(source):
    target = " ".join([source.get("title") or "", source.get("url") or ""]).lower()
    return "infomoney.com.br" in target


def _agrinvest_credentials_configured():
    return bool(
        (getattr(settings, "AGRINVEST_USERNAME", "") or "").strip()
        and (getattr(settings, "AGRINVEST_PASSWORD", "") or "").strip()
    )


def _agrinvest_login_external():
    username = (getattr(settings, "AGRINVEST_USERNAME", "") or "").strip()
    password = (getattr(settings, "AGRINVEST_PASSWORD", "") or "").strip()
    if not username or not password:
        raise RuntimeError("Credenciais da Agrinvest nao configuradas no backend.")

    client_id = (getattr(settings, "AGRINVEST_CLIENT_ID", "") or "").strip() or "D2365402-2F59-4627-A73D-71814F8FCCD2"
    request = urllib.request.Request(
        "https://agrinvest-account-api.azurewebsites.net/api/account/login-external",
        data=json.dumps({"email": username, "password": password}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "client_id": client_id,
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("data") or {}


def _agrinvest_build_opener():
    jar = CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar


def _agrinvest_fetch(opener, url, *, data=None, headers=None, method=None):
    request = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "Mozilla/5.0", **(headers or {})},
        method=method,
    )
    with opener.open(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _agrinvest_portal_login():
    opener, jar = _agrinvest_build_opener()
    login_data = _agrinvest_login_external()
    external_token = str(login_data.get("accessExternalToken") or "").strip()
    if not external_token:
        raise RuntimeError("Agrinvest: login externo sem external token.")

    auth_url = "https://go.agrinvest.agr.br/auth?" + urllib.parse.urlencode({"externalToken": external_token})
    auth_html = _agrinvest_fetch(opener, auth_url)

    csrf_match = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', auth_html)
    external_match = re.search(r'name="externalToken" type="hidden" value="([^"]*)"', auth_html)
    csrf_token = csrf_match.group(1) if csrf_match else ""
    exchange_token = external_match.group(1) if external_match else ""
    if not csrf_token or not exchange_token:
        raise RuntimeError("Agrinvest: nao foi possivel preparar a autenticacao do portal.")

    post_data = urllib.parse.urlencode(
        {
            "accessExternalToken": exchange_token,
            "__RequestVerificationToken": csrf_token,
        }
    ).encode("utf-8")
    login_response = _agrinvest_fetch(
        opener,
        "https://go.agrinvest.agr.br/account/login",
        data=post_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": auth_url,
        },
        method="POST",
    )
    payload = json.loads(login_response or "{}")
    if not payload.get("Success"):
        raise RuntimeError("Agrinvest: falha ao abrir sessao no portal de noticias.")

    refresh = (((payload.get("JsonContent") or {}).get("Data") or {}).get("refresh")) or ""
    return opener, jar, refresh


def _extract_agrinvest_recent_links(list_html, limit=5):
    entries = []
    pattern = re.compile(
        r'<a href="/noticias/details/(?P<id>\d+)"[^>]*>\s*(?P<title>.*?)\s*</a>.*?'
        r'(?P<date>\d{2}/\d{2}/\d{4}).*?'
        r'<a href="/noticias/details/\d+"[^>]*>\s*(?P<preview>.*?)\s*</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(list_html):
        entry = {
            "title": _strip_tags(match.group("title")),
            "date": _strip_tags(match.group("date")),
            "preview": _strip_tags(match.group("preview")),
            "url": f"https://go.agrinvest.agr.br/noticias/details/{match.group('id')}",
        }
        if not entry["title"]:
            continue
        if entry not in entries:
            entries.append(entry)
        if len(entries) >= limit:
            break
    return entries


def _extract_agrinvest_article(detail_html, url):
    title_match = re.search(r'<div class="titulo">.*?<h2[^>]*>(.*?)</h2>', detail_html, flags=re.IGNORECASE | re.DOTALL)
    meta_match = re.search(r'<div class="infoAuthors.*?<p>(.*?)</p>', detail_html, flags=re.IGNORECASE | re.DOTALL)
    body_match = re.search(r'<div id="div-post-content">(.*?)</div>', detail_html, flags=re.IGNORECASE | re.DOTALL)

    title = _strip_tags(title_match.group(1)) if title_match else ""
    meta = _html_to_text(meta_match.group(1)) if meta_match else ""
    body = _html_to_text(body_match.group(1)) if body_match else ""
    return {
        "title": title,
        "meta": meta,
        "body": body,
        "url": url,
    }


def _fetch_agrinvest_article(opener, url):
    html_text = _agrinvest_fetch(opener, url, headers={"Referer": "https://go.agrinvest.agr.br/noticias"})
    article = _extract_agrinvest_article(html_text, url)
    if not article["body"]:
        raise RuntimeError(f"Agrinvest: nao foi possivel extrair o conteudo de {url}.")
    return article


def _fetch_agrinvest_authenticated_digest(source_url):
    opener, _jar, _refresh = _agrinvest_portal_login()
    target_url = (source_url or "").strip() or (getattr(settings, "AGRINVEST_NEWS_URL", "") or "").strip() or "https://go.agrinvest.agr.br/noticias"

    if "/noticias/details/" in target_url:
        article = _fetch_agrinvest_article(opener, target_url)
        lines = ["Conteudo autenticado da Agrinvest:"]
        lines.append(f"TITULO: {article['title']}")
        if article["meta"]:
            lines.append(f"META: {article['meta']}")
        lines.append(f"LINK: {article['url']}")
        lines.append("TEXTO:")
        lines.append(article["body"][:12000])
        return "\n".join(lines)

    list_html = _agrinvest_fetch(opener, target_url)
    recent_entries = _extract_agrinvest_recent_links(list_html, limit=5)
    if not recent_entries:
        raise RuntimeError("Agrinvest: nao foi possivel localizar noticias recentes.")

    blocks = ["Materias autenticadas da Agrinvest:"]
    for item in recent_entries:
        article = _fetch_agrinvest_article(opener, item["url"])
        blocks.append(f"## {article['title'] or item['title']}")
        if article["meta"]:
            blocks.append(article["meta"])
        blocks.append(f"Link: {item['url']}")
        if item["preview"]:
            blocks.append(f"Preview da listagem: {item['preview']}")
        blocks.append(article["body"][:5000])
    return "\n\n".join(blocks)


def _fetch_agrinvest_public_digest():
    news_url = (getattr(settings, "AGRINVEST_NEWS_URL", "") or "").strip() or "https://go.agrinvest.agr.br/noticias"
    body = _fetch_text(news_url)
    entries = _extract_agrinvest_recent_links(body, limit=8)

    if not entries:
        raise RuntimeError("Nao foi possivel extrair destaques publicos da Agrinvest.")

    lines = ["Destaques recentes da Agrinvest (listagem publica):"]
    for item in entries:
        line = f"- {item['date']} | {item['title']}"
        if item["preview"]:
            line += f" | Preview: {item['preview']}"
        line += f" | Link: {item['url']}"
        lines.append(line)
    return "\n".join(lines)


def _iter_listing_links(list_html, base_url):
    for match in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', list_html, flags=re.IGNORECASE | re.DOTALL):
        url = _normalize_link(base_url, match.group(1))
        title = _strip_tags(match.group(2))
        if not url or not title:
            continue
        yield {"url": url, "title": title}


def _extract_noticias_agricolas_recent_links(list_html, base_url):
    entries = []
    seen = set()
    for item in _iter_listing_links(list_html, base_url):
        parsed = urllib.parse.urlparse(item["url"])
        if parsed.netloc and "noticiasagricolas.com.br" not in parsed.netloc:
            continue
        if "/noticias/" not in parsed.path or parsed.path.rstrip("/") == "/noticias":
            continue
        if not parsed.path.endswith(".html"):
            continue
        if any(token in parsed.path for token in ["/videos/", "/tempo-e-dinheiro/", "/quentes/"]):
            continue
        key = item["url"]
        if key in seen:
            continue
        seen.add(key)
        entries.append(item)
        if len(entries) >= AUTO_SOURCE_LIMIT * 3:
            break
    return entries


def _extract_infomoney_recent_links(list_html, base_url):
    entries = []
    seen = set()
    for item in _iter_listing_links(list_html, base_url):
        parsed = urllib.parse.urlparse(item["url"])
        if parsed.netloc and "infomoney.com.br" not in parsed.netloc:
            continue
        if "/economia/" not in parsed.path or parsed.path.rstrip("/") == "/economia":
            continue
        if any(token in parsed.path for token in ["/tag/", "/categoria/", "/author/"]):
            continue
        key = item["url"]
        if key in seen:
            continue
        seen.add(key)
        entries.append(item)
        if len(entries) >= AUTO_SOURCE_LIMIT * 3:
            break
    return entries


def _fetch_public_source_digest(source):
    base_url = str(source.get("url") or "").strip()
    if not base_url:
        raise RuntimeError("Fonte sem URL para busca automatica.")

    list_html = _fetch_text(base_url)
    if _is_noticias_agricolas_source(source):
        entries = _extract_noticias_agricolas_recent_links(list_html, base_url)
    elif _is_infomoney_source(source):
        entries = _extract_infomoney_recent_links(list_html, base_url)
    else:
        raise RuntimeError("Busca automatica nao suportada para esta fonte.")

    if not entries:
        raise RuntimeError("Nenhuma materia recente encontrada na fonte.")

    cutoff = _parse_recent_cutoff()
    articles = []
    for item in entries:
        try:
            page_html = _fetch_text(item["url"], headers={"Referer": base_url})
        except Exception:
            continue

        article = {
            "title": _extract_meta_content(page_html, "og:title") or item["title"],
            "url": item["url"],
            "published_at": _extract_article_date(page_html),
            "body": _extract_article_text(page_html),
        }
        if not article["body"]:
            continue

        published_at = _parse_article_date(article["published_at"])
        if published_at and published_at < cutoff:
            continue

        articles.append(article)
        if len(articles) >= AUTO_SOURCE_LIMIT:
            break

    if not articles:
        raise RuntimeError("Nao encontrei materias recentes com conteudo suficiente na fonte.")

    blocks = [f"Noticias recentes coletadas automaticamente de {source['title']}:"]
    for article in articles:
        blocks.append(f"## {article['title']}")
        if article["published_at"]:
            blocks.append(f"Data: {article['published_at']}")
        blocks.append(f"Link: {article['url']}")
        blocks.append(article["body"])
    return "\n\n".join(blocks)


def _hydrate_known_sources(sources, warnings, *, use_source_search=False):
    hydrated = []
    agrinvest_digest = None
    agrinvest_login_checked = False

    for source in sources:
        next_source = dict(source)

        if _is_agrinvest_source(next_source) and not next_source.get("content"):
            if _agrinvest_credentials_configured() and not agrinvest_login_checked:
                agrinvest_login_checked = True
                try:
                    agrinvest_digest = _fetch_agrinvest_authenticated_digest(next_source.get("url"))
                except Exception:
                    agrinvest_digest = ""
                    warnings.append(
                        "Agrinvest: credenciais validadas, mas a coleta autenticada completa falhou; usei o fallback publico quando disponivel."
                    )
                else:
                    warnings.append("Agrinvest: materias autenticadas carregadas automaticamente no backend.")

            if agrinvest_digest is None:
                try:
                    agrinvest_digest = _fetch_agrinvest_public_digest()
                except (RuntimeError, urllib.error.URLError):
                    agrinvest_digest = ""
                    warnings.append("Agrinvest: nao foi possivel carregar automaticamente os destaques publicos no momento.")

            if agrinvest_digest:
                next_source["content"] = agrinvest_digest

        if use_source_search and next_source.get("url"):
            try:
                digest = _fetch_public_source_digest(next_source)
            except Exception as exc:
                warnings.append(f"{next_source['title']}: busca automatica indisponivel agora ({exc}).")
            else:
                next_source["content"] = digest if not next_source.get("content") else f"{next_source['content']}\n\n{digest}"
                warnings.append(f"{next_source['title']}: noticias recentes coletadas automaticamente no backend.")

        hydrated.append(next_source)

    return hydrated


def _build_outline_guidance(outline):
    titles = [line.strip() for line in str(outline or "").splitlines() if line.strip()]
    guidance = []
    for title in titles:
        style = "bullet points curtos e objetivos" if title.lower() in BULLET_SECTION_TITLES else "texto corrido em um ou dois paragrafos"
        guidance.append(f"- {title}: {style}. Se faltar base factual, escrever exatamente 'sem noticias relevantes'.")
    return "\n".join(guidance)


def _call_openai_market_summary(payload):
    api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY nao configurada.")

    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("Biblioteca OpenAI indisponivel no backend.") from exc

    model = getattr(settings, "OPENAI_MARKET_SUMMARY_MODEL", "") or getattr(settings, "OPENAI_INSIGHTS_MODEL", "gpt-5-mini")
    client = OpenAI(api_key=api_key, timeout=60.0, max_retries=0)

    instructions = (
        "Voce e um analista senior de mercado agricola brasileiro. "
        "Sua tarefa e escrever um resumo semanal de mercado em portugues do Brasil, "
        "com linguagem executiva, clara, objetiva e util para produtor rural. "
        "Use somente o material fornecido nas fontes. Nao invente dados, fatos, numeros ou citacoes. "
        "Para cada secao da estrutura, mantenha o titulo em Markdown e preencha o conteudo logo abaixo. "
        "Quando faltar base para uma secao, escreva exatamente: sem noticias relevantes. "
        "Respeite o estilo indicado para cada item: alguns em bullet points e outros em texto corrido. "
        "Entregue apenas o resumo final em Markdown, sem cercas de codigo e sem comentarios extras."
    )

    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": (
                        "Objetivo:\n"
                        f"{payload['objective']}\n\n"
                        "Estrutura sugerida:\n"
                        f"{payload['outline']}\n\n"
                        "Orientacao de formato por secao:\n"
                        f"{payload['outline_guidance']}\n\n"
                        "Fontes disponiveis:\n"
                        f"{payload['sources']}\n\n"
                        "Monte um resumo semanal de mercado completo, consolidado e pronto para revisao."
                    ),
                },
            ],
        )
    except Exception as exc:
        raise RuntimeError(f"OpenAI: {exc}") from exc

    output_text = (getattr(response, "output_text", None) or "").strip()
    if not output_text:
        raise RuntimeError("A IA nao retornou conteudo.")

    return {"model": model, "summary": output_text}


def generate_market_summary(payload):
    objective = str(payload.get("objective") or "").strip() or DEFAULT_MARKET_SUMMARY_OBJECTIVE
    outline = str(payload.get("outline") or "").strip() or DEFAULT_MARKET_SUMMARY_OUTLINE
    use_source_search = bool(payload.get("use_source_search"))
    sources_raw = payload.get("sources")
    sources_items = sources_raw if isinstance(sources_raw, list) else []
    sources = []
    warnings = []

    for index, item in enumerate(sources_items):
        if not isinstance(item, dict):
            continue
        normalized = _normalize_source(item, index)
        if not normalized:
            continue
        if normalized["url"] and not normalized["content"] and not use_source_search:
            warnings.append(
                f"{normalized['title']}: URL informada sem trecho/resumo. Ative a busca automatica para a IA varrer noticias recentes dessa fonte."
            )
        sources.append(normalized)

    if not sources:
        sources = [
            _normalize_source(item, index)
            for index, item in enumerate(DEFAULT_MARKET_SUMMARY_SOURCES)
        ]
        sources = [item for item in sources if item]

    sources = _hydrate_known_sources(sources, warnings, use_source_search=use_source_search)

    if not any(str(item.get("content") or "").strip() for item in sources):
        raise ValueError("Nao encontrei conteudo suficiente nas fontes. Cole anotacoes manualmente ou ative a busca automatica.")

    outline_guidance = _build_outline_guidance(outline)
    ai_result = _call_openai_market_summary(
        {
            "objective": objective,
            "outline": outline,
            "outline_guidance": outline_guidance,
            "sources": sources[:24],
        }
    )

    return {
        "summary": ai_result["summary"],
        "model": ai_result["model"],
        "objective": objective,
        "outline": outline,
        "warnings": warnings,
        "source_count": len(sources),
        "use_source_search": use_source_search,
    }
