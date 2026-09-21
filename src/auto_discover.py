from __future__ import annotations

import logging
import os
import random
import re

from src.llm import chat_json_object, get_model, llm_configured

from src.schemas import Source

logger = logging.getLogger(__name__)

_SKIP_URL_PARTS = (
    "wikipedia.org",
    "linkedin.com/jobs",
    "indeed.com/jobs",
    "glassdoor.com",
    "crunchbase.com/lists",
)

_SKIP_TITLE_HINTS = (
    "top ",
    "best ",
    "10 best",
    "list of",
    "wikipedia",
    "news -",
    "breaking:",
)

_STARTUP_HINTS = ("startup", "founded", "launched", "seed", "pre-seed", "accelerator", "2025", "2026")


def parse_exclude_list(*parts: str | None) -> list[str]:
    """Lowercase needles; supports comma-separated strings and repeated flags."""
    needles: list[str] = []
    for part in parts:
        if not part or not str(part).strip():
            continue
        for piece in str(part).split(","):
            p = piece.strip().lower()
            if p and p not in needles:
                needles.append(p)
    return needles


def _matches_exclude(title: str, excerpt: str, exclude: list[str]) -> bool:
    if not exclude:
        return False
    blob = f"{title} {excerpt}".lower()
    return any(needle in blob for needle in exclude)


def _name_is_excluded(name: str, exclude: list[str]) -> bool:
    if not exclude:
        return False
    lower = name.lower()
    return any(needle in lower for needle in exclude)


def _title_to_name(title: str) -> str:
    return re.split(r"\s[-|]\s", title, maxsplit=1)[0].strip().strip(" |-")[:90]


def _collect_candidate_names(
    sources: list[Source],
    *,
    exclude: list[str],
    prefer_startup_hints: bool,
) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def try_add(s: Source) -> None:
        if _matches_exclude(s.title, s.excerpt, exclude):
            return
        u = s.url.lower()
        if any(p in u for p in _SKIP_URL_PARTS):
            return
        t = s.title.lower()
        if any(h in t for h in _SKIP_TITLE_HINTS):
            return
        if prefer_startup_hints:
            blob = f"{s.title} {s.excerpt}".lower()
            if not any(h in blob for h in _STARTUP_HINTS):
                return
        name = _title_to_name(s.title)
        if not (3 <= len(name) <= 90):
            return
        if _name_is_excluded(name, exclude):
            return
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        ordered.append(name)

    for s in sources:
        try_add(s)
    if not ordered and not prefer_startup_hints:
        for s in sources:
            try_add(s)
    return ordered


def pick_business_name_heuristic(
    sources: list[Source],
    exclude: list[str],
    *,
    variety: bool,
) -> str:
    candidates = _collect_candidate_names(sources, exclude=exclude, prefer_startup_hints=True)
    if not candidates:
        candidates = _collect_candidate_names(sources, exclude=exclude, prefer_startup_hints=False)
    if not candidates:
        return _pick_first_valid_title(sources, exclude=exclude)
    if variety and len(candidates) > 1:
        return random.choice(candidates[:8])
    return candidates[0]


def _pick_first_valid_title(sources: list[Source], exclude: list[str]) -> str:
    for s in sources:
        if _matches_exclude(s.title, s.excerpt, exclude):
            continue
        u = s.url.lower()
        if any(p in u for p in _SKIP_URL_PARTS):
            continue
        t = s.title.lower()
        if any(h in t for h in _SKIP_TITLE_HINTS):
            continue
        name = _title_to_name(s.title)
        if name and not _name_is_excluded(name, exclude):
            return name
    if sources:
        fallback = _title_to_name(sources[0].title)
        if not _name_is_excluded(fallback, exclude):
            return fallback
    return "Unknown"


def pick_business_name_llm(
    sources: list[Source],
    vertical: str,
    area: str,
    *,
    exclude: list[str],
    variety: bool,
) -> str | None:
    model = get_model()
    lines = [
        f"Vertical: {vertical}",
        f"Area: {area}",
        "Pick a startup that appears to be about **12 months old or less** when snippets support it.",
        "",
    ]
    if exclude:
        lines.append("Do NOT select any of these (or essentially the same company):")
        for item in exclude[:20]:
            lines.append(f"- {item}")
        lines.append("")
    lines.append("Search results (title | url | excerpt):")
    for i, s in enumerate(sources[:22], start=1):
        ex = s.excerpt[:400].replace("\n", " ")
        lines.append(f"{i}. {s.title}\n   {s.url}\n   {ex}")
    user = "\n".join(lines)

    system = """You help a consultant pick ONE real, operating **young startup** to research next.
Prefer companies with signals: founded/launched recently (2025–2026), seed/pre-seed, accelerator, "new startup", first product launch.
Avoid directories, listicles, job boards, and mature enterprises unless snippets clearly show a brand-new unit.

Return a single json object with keys:
"business_name" (string),
"confidence" ("high"|"medium"|"low"),
"reason" (one short sentence: age signal + why AWS/dev consulting may fit).

Rules:
- Must be one identifiable startup/company, not a list article.
- Must NOT match any name on the user's exclusion list.
- If age cannot be confirmed, pick the best candidate but set confidence "low" and say age unconfirmed in reason.
- business_name must not contain quotes or newlines."""

    data = chat_json_object(
        system=system,
        user=user,
        temperature=0.7 if variety else 0.15,
        model=model,
    )
    name = str(data.get("business_name") or "").strip()
    if not name:
        return None
    if _name_is_excluded(name, exclude):
        return None
    return name


def pick_business_name(
    sources: list[Source],
    *,
    vertical: str,
    area: str,
    use_llm: bool,
    exclude: list[str] | None = None,
    variety: bool = False,
) -> tuple[str, str]:
    """Return (business_name, how_it_was_chosen)."""
    needles = exclude or []
    if not sources:
        return "Unknown", "No search results."

    working = list(sources)
    if variety:
        random.shuffle(working)

    if use_llm and llm_configured():
        try:
            name = pick_business_name_llm(
                working,
                vertical,
                area,
                exclude=needles,
                variety=variety,
            )
            if name:
                note = (
                    "Selected young startup with LLM from search snippets—"
                    "**verify age and contacts** before outreach."
                )
                if variety:
                    note += " (`--variety` enabled.)"
                if needles:
                    note += f" (Excluded {len(needles)} name(s).)"
                return name, note
        except Exception:
            logger.exception("LLM business pick failed")

    name = pick_business_name_heuristic(working, needles, variety=variety)
    note = (
        "Heuristic pick (startup keywords in titles)—**verify**; "
        "use LLM pick for better age filtering."
    )
    if variety:
        note += " (`--variety` enabled.)"
    if needles:
        note += f" (Excluded {len(needles)} name(s).)"
    return name, note
