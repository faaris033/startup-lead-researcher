from __future__ import annotations

import logging
from collections.abc import Iterable

from ddgs import DDGS

from src.schemas import Source

logger = logging.getLogger(__name__)


def _dedupe_by_url(sources: Iterable[Source]) -> list[Source]:
    seen: set[str] = set()
    out: list[Source] = []
    for s in sources:
        if s.url in seen:
            continue
        seen.add(s.url)
        out.append(s)
    return out


def _queries_for_target(
    company: str,
    *,
    locality: str | None,
    industry: str | None,
) -> list[str]:
    c = company.strip()
    loc = (locality or "").strip()
    ind = (industry or "").strip()

    if loc:
        qs = [
            f'"{c}" {loc} startup founded OR launched',
            f'"{c}" {loc} contact email phone',
            f'"{c}" {loc} seed funding OR accelerator',
            f'"{c}" {loc} technology software',
        ]
        if ind:
            qs.append(f'"{c}" {loc} {ind} startup')
        return qs

    qs = [
        f'"{c}" startup founded OR launched 2025 2026',
        f'"{c}" contact email phone',
        f'"{c}" funding seed pre-seed',
    ]
    if ind:
        qs.append(f'"{c}" {ind} startup')
    return qs


def search_public_signals(
    company: str,
    *,
    locality: str | None = None,
    industry: str | None = None,
    max_per_query: int = 8,
) -> list[Source]:
    """Public web snippets skewed toward young startups and contact hints."""
    queries = _queries_for_target(company, locality=locality, industry=industry)
    collected: list[Source] = []
    try:
        with DDGS() as ddgs:
            for q in queries:
                for row in ddgs.text(q, max_results=max_per_query):
                    title = (row.get("title") or "").strip() or "Untitled"
                    href = (row.get("href") or "").strip()
                    body = (row.get("body") or "").strip()
                    if not href:
                        continue
                    collected.append(Source(title=title, url=href, excerpt=body[:1200]))
    except Exception:
        logger.exception("Web search failed")
        return []
    return _dedupe_by_url(collected)[:22]


def search_contact_signals(
    company: str,
    *,
    locality: str | None = None,
    max_per_query: int = 10,
    max_total: int = 18,
) -> list[Source]:
    """Extra searches aimed at pages/snippets that often list phone/email."""
    c = company.strip()
    loc = (locality or "").strip()
    queries = [
        f'"{c}" contact email phone',
        f'"{c}" "contact us"',
        f'"{c}" info@ OR hello@ OR support@ OR sales@',
    ]
    if loc:
        queries.extend(
            [
                f'"{c}" {loc} phone',
                f'"{c}" {loc} email address',
            ],
        )
    queries.append(f'site:linkedin.com "{c}"')

    collected: list[Source] = []
    try:
        with DDGS() as ddgs:
            for q in queries:
                try:
                    rows = ddgs.text(q, max_results=max_per_query)
                except Exception as exc:
                    logger.debug("Contact query %r skipped: %s", q, exc)
                    continue
                for row in rows:
                    title = (row.get("title") or "").strip() or "Untitled"
                    href = (row.get("href") or "").strip()
                    body = (row.get("body") or "").strip()
                    if not href:
                        continue
                    collected.append(Source(title=title, url=href, excerpt=body[:1200]))
    except Exception:
        logger.exception("Contact-focused search failed")
        return []
    return _dedupe_by_url(collected)[:max_total]


def merge_source_lists(*lists: list[Source], max_total: int = 32) -> list[Source]:
    return _dedupe_by_url([s for lst in lists for s in lst])[:max_total]


def search_vertical_in_area(
    vertical: str,
    area: str,
    *,
    query_variant: int = 0,
    max_per_query: int = 10,
    max_total: int = 28,
) -> list[Source]:
    """Search for new startups in an area (founded ~last year when snippets mention it)."""
    v = vertical.strip() or "startup"
    a = area.strip()
    if not a:
        return []
    k = query_variant % 4
    alts = [
        f"startup {a} founded 2025 OR 2026",
        f"new startup {v} {a} launched",
        f"seed stage startup {a}",
        f"pre-seed startup {a} {v}",
    ]
    queries = [
        f"startup {v} {a} founded OR launched",
        f"early stage startup {a} hiring engineers",
        alts[k],
    ]
    collected: list[Source] = []
    try:
        with DDGS() as ddgs:
            for q in queries:
                for row in ddgs.text(q, max_results=max_per_query):
                    title = (row.get("title") or "").strip() or "Untitled"
                    href = (row.get("href") or "").strip()
                    body = (row.get("body") or "").strip()
                    if not href:
                        continue
                    collected.append(Source(title=title, url=href, excerpt=body[:1200]))
    except Exception:
        logger.exception("Web search failed")
        return []
    return _dedupe_by_url(collected)[:max_total]
