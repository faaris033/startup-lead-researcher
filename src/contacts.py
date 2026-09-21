from __future__ import annotations

import re
from urllib.parse import urlparse

from src.schemas import ContactLead, Source

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(
    r"(?:\+1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b",
)
_MAILTO_RE = re.compile(r"mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", re.I)
_TEL_RE = re.compile(r"tel:([+\d().\s-]{10,20})", re.I)
_LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[A-Za-z0-9._%-]+/?",
    re.I,
)

_JUNK_EMAIL_SUFFIXES = (
    "@example.com",
    "@sentry.io",
    "@wixpress.com",
    "@schema.org",
    "@2x.png",
    "@3x.jpg",
)
_JUNK_EMAIL_LOCAL = ("noreply", "no-reply", "donotreply", "mailer-daemon", "wordpress")

_JUNK_WEBSITE_HOSTS = (
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "youtube.com",
    "google.com",
    "bing.com",
    "wikipedia.org",
    "indeed.com",
    "glassdoor.com",
    "crunchbase.com",
    "yahoo.com",
    "reddit.com",
    "gov",
    "interglobix",
    "milldampr.com",
)


def _is_plausible_email(email: str) -> bool:
    e = email.lower().strip()
    if any(e.endswith(s) for s in _JUNK_EMAIL_SUFFIXES):
        return False
    if any(x in e.split("@")[0] for x in _JUNK_EMAIL_LOCAL):
        return False
    if len(e) < 6 or ".." in e:
        return False
    return True


def _normalize_phone(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw).strip()
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return cleaned


def extract_contacts_from_text(text: str, *, source_hint: str = "") -> list[ContactLead]:
    out: list[ContactLead] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str) -> None:
        v = value.strip()
        if not v:
            return
        key = (kind, v.lower())
        if key in seen:
            return
        seen.add(key)
        out.append(ContactLead(kind=kind, value=v, evidence=source_hint or "Found in web snippet"))

    for m in _MAILTO_RE.findall(text):
        if _is_plausible_email(m):
            add("email", m)
    for m in _EMAIL_RE.findall(text):
        if _is_plausible_email(m):
            add("email", m)
    for m in _TEL_RE.findall(text):
        add("phone", _normalize_phone(m))
    for m in _PHONE_RE.findall(text):
        add("phone", _normalize_phone(m))
    for m in _LINKEDIN_RE.findall(text):
        add("linkedin", m.rstrip("/"))

    return out


_SKIP_TOKENS = frozenset(
    {"the", "and", "inc", "llc", "ltd", "corp", "co", "company", "startup", "technologies"},
)


def _company_tokens(company: str) -> list[str]:
    return [
        t.lower()
        for t in re.findall(r"[A-Za-z0-9]{3,}", company)
        if t.lower() not in _SKIP_TOKENS
    ]


def _source_matches_company(source: Source, tokens: list[str]) -> bool:
    if not tokens:
        return True
    blob = f"{source.title} {source.url} {source.excerpt}".lower()
    return any(t in blob for t in tokens)


def _is_noise_source(source: Source, tokens: list[str]) -> bool:
    url = source.url.lower()
    if ".gov" in url and tokens and not _source_matches_company(source, tokens):
        return True
    if any(x in url for x in ("/aclick?", "bing.com/aclick")):
        return True
    return False


def extract_contacts_from_sources(
    sources: list[Source],
    *,
    company: str | None = None,
) -> list[ContactLead]:
    tokens = _company_tokens(company or "")
    pool = [s for s in sources if not _is_noise_source(s, tokens)]
    relevant = [s for s in pool if _source_matches_company(s, tokens)] if tokens else pool
    if relevant:
        pool = relevant

    merged: list[ContactLead] = []
    seen: set[tuple[str, str]] = set()
    for s in pool:
        blob = f"{s.title} {s.url} {s.excerpt}"
        hint = f"{s.title[:60]} — {s.url[:80]}"
        for c in extract_contacts_from_text(blob, source_hint=hint):
            key = (c.kind, c.value.lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append(c)
    return merged


def _normalize_site_url(url: str) -> str | None:
    raw = url.strip()
    if not raw.startswith(("http://", "https://")):
        return None
    parsed = urlparse(raw)
    if not parsed.netloc:
        return None
    host = parsed.netloc.lower().removeprefix("www.")
    if any(j in host for j in _JUNK_WEBSITE_HOSTS):
        return None
    return f"{parsed.scheme}://{parsed.netloc}/"


def extract_company_websites(
    sources: list[Source],
    company: str,
    *,
    max_sites: int = 3,
) -> list[tuple[str, str]]:
    """Return (homepage_url, evidence) guesses from search result URLs."""
    tokens = _company_tokens(company)
    scored: list[tuple[int, str, str]] = []
    seen_hosts: set[str] = set()

    for s in sources:
        if _is_noise_source(s, tokens):
            continue
        site = _normalize_site_url(s.url)
        if not site:
            continue
        host = urlparse(site).netloc.lower().removeprefix("www.")
        if host in seen_hosts:
            continue
        seen_hosts.add(host)
        score = 0
        if tokens and any(t in host for t in tokens):
            score += 12
        if _source_matches_company(s, tokens):
            score += 6
        path = urlparse(s.url).path
        if path in ("", "/"):
            score += 4
        hint = f"{s.title[:60]} — {s.url[:80]}"
        scored.append((score, site, hint))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return [(url, hint) for _, url, hint in scored[:max_sites]]


def enrich_contact_leads(
    contacts: list[ContactLead],
    sources: list[Source],
    *,
    company: str,
) -> list[ContactLead]:
    """When phone/email are missing, add company website link(s) under kind other."""
    out = list(contacts)
    seen = {(c.kind.lower(), c.value.strip().lower()) for c in out}
    has_phone = any(c.kind.lower() == "phone" for c in out)
    has_email = any(c.kind.lower() == "email" for c in out)
    sites = extract_company_websites(sources, company)

    for url, evidence in sites:
        key = ("website", url.lower())
        if key not in seen:
            seen.add(key)
            out.append(ContactLead(kind="website", value=url, evidence=evidence))

    if not has_phone and not has_email and sites:
        url, evidence = sites[0]
        key = ("other", url.lower())
        if key not in seen:
            seen.add(key)
            out.append(
                ContactLead(
                    kind="other",
                    value=url,
                    evidence=f"No verified phone/email in snippets — find contacts on site. {evidence}",
                ),
            )

    return out


_MAX_PHONES = 2
_MAX_EMAILS = 2
_MIN_CONTACT_SCORE = 8

_TOLL_FREE_PREFIXES = ("800", "833", "844", "855", "866", "877", "888")
_GENERIC_EMAIL_DOMAINS = frozenset(
    {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "proton.me", "protonmail.com"},
)


def _phone_digits(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def _score_contact(c: ContactLead, tokens: list[str]) -> int:
    kind = (c.kind or "").lower()
    evidence = (c.evidence or "").lower()
    value = (c.value or "").strip().lower()
    score = 0

    if ".gov" in evidence:
        score -= 50
    if any(x in evidence for x in ("indeed.com", "glassdoor.com", "wikipedia.org", "bing.com/aclick")):
        score -= 25
    if tokens and any(t in evidence for t in tokens):
        score += 14
    if "contact" in evidence or "/contact" in evidence:
        score += 10

    if kind == "phone":
        digits = _phone_digits(c.value)
        if len(digits) != 10:
            score -= 20
        if digits.startswith(_TOLL_FREE_PREFIXES):
            score -= 12
        if "tel:" in evidence:
            score += 12
    elif kind == "email":
        local, _, domain = value.partition("@")
        if "mailto:" in evidence:
            score += 12
        if tokens and domain and any(t in domain for t in tokens):
            score += 22
        if local in ("info", "hello", "contact", "sales", "support", "team"):
            score += 8
        if domain in _GENERIC_EMAIL_DOMAINS:
            score += 3
    elif kind == "linkedin":
        score += 5
    elif kind == "website":
        score += 4

    return score


def curate_contact_leads(
    contacts: list[ContactLead],
    *,
    company: str,
    max_phones: int = _MAX_PHONES,
    max_emails: int = _MAX_EMAILS,
) -> list[ContactLead]:
    """Keep at most 1–2 best-scoring phones/emails; drop low-confidence matches."""
    tokens = _company_tokens(company)
    phones = [c for c in contacts if (c.kind or "").lower() == "phone"]
    emails = [c for c in contacts if (c.kind or "").lower() == "email"]
    rest = [c for c in contacts if (c.kind or "").lower() not in ("phone", "email")]

    phones.sort(key=lambda c: (-_score_contact(c, tokens), c.value))
    emails.sort(key=lambda c: (-_score_contact(c, tokens), c.value))

    picked_phones: list[ContactLead] = []
    seen_digits: set[str] = set()
    for p in phones:
        if len(picked_phones) >= max_phones:
            break
        if _score_contact(p, tokens) < _MIN_CONTACT_SCORE:
            continue
        digits = _phone_digits(p.value)
        if digits in seen_digits:
            continue
        seen_digits.add(digits)
        picked_phones.append(p)

    picked_emails: list[ContactLead] = []
    seen_emails: set[str] = set()
    for e in emails:
        if len(picked_emails) >= max_emails:
            break
        if _score_contact(e, tokens) < _MIN_CONTACT_SCORE:
            continue
        key = e.value.strip().lower()
        if key in seen_emails:
            continue
        seen_emails.add(key)
        picked_emails.append(e)

    # At most one LinkedIn and one website in the rest
    linkedin = [c for c in rest if (c.kind or "").lower() == "linkedin"][:1]
    websites = [c for c in rest if (c.kind or "").lower() == "website"][:1]
    other = [c for c in rest if (c.kind or "").lower() not in ("linkedin", "website")][:1]

    return picked_phones + picked_emails + linkedin + websites + other


def merge_contact_leads(*groups: list[ContactLead]) -> list[ContactLead]:
    out: list[ContactLead] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for c in group:
            if not (c.value or "").strip():
                continue
            key = (c.kind.lower(), c.value.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
    return out
