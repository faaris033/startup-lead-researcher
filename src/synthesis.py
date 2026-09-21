from __future__ import annotations

import os

from src.llm import chat_json_object, get_model

from src.schemas import ContactLead, LeadBrief, Source

_JSON_KEYS = """
You MUST respond with a single valid json object (no markdown fences) using exactly these keys:
"executive_summary", "company_age_signal", "hypotheses", "discovery_questions", "talking_points", "contact_leads".
Arrays must have at least 3 items when snippets support it. contact_leads may be empty if nothing is in snippets.
"""

_CONTACT_RULES = """
contact_leads: array of 0-6 objects, each with "kind" (phone|email|website|linkedin|other), "value", "evidence".
CRITICAL: Read snippets for phones/emails on the company's own site or contact page only—never invent values.
Include at most **2 phones** and **2 emails** that clearly belong to this company (prefer company-domain email and numbers on their contact page).
If unsure, omit rather than guess. If none found, use [] (website fallback is added separately).
If no phone/email but a company homepage URL is in snippets, add it as kind "other" or "website" (never invent URLs).
If truly none found, use [] and mention that in company_age_signal or executive_summary.
"""

_STARTUP_RULES = """
Target: a **young startup** (~12 months old or less **only when snippets support it**—e.g. founded/launched 2025–2026,
"just opened", seed/pre-seed, accelerator, "new startup"). If age is unclear, say so in company_age_signal—do not invent a founding date.
Consulting fit: **AWS/cloud** (hosting, MVP infra, CI/CD, cost control) AND **software development** (MVP build, integrations, small team delivery).
"""

_SYSTEM = f"""You prepare outreach research for a consultant selling AWS/cloud and hands-on software development to early-stage startups.

{_JSON_KEYS}
{_STARTUP_RULES}
{_CONTACT_RULES}

Field guidance:
- executive_summary: 2-4 sentences (what they do, stage signal, why they might need cloud or dev help)
- company_age_signal: 1-2 sentences on evidence of being ~1 year old or less—or "Age not confirmed in snippets"
- hypotheses: 4-7 pains (MVP hosting, no DevOps, manual deploys, founder-built spaghetti, security gaps, surprise bills, need contract dev)
- discovery_questions: 5-8 questions (stack, where app runs, releases, team technical depth, runway, build vs buy)
- talking_points: 4-7 bullets mixing AWS (Lambda/ECS, RDS, S3, IAM, CloudWatch) and dev consulting (MVP, APIs, integrations)—tied to snippets

Do not invent funding amounts, customers, or addresses not in snippets.
"""


def _parse_contacts(raw_list: object) -> list[ContactLead]:
    out: list[ContactLead] = []
    if not isinstance(raw_list, list):
        return out
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "other").strip().lower() or "other"
        value = str(item.get("value") or "").strip()
        evidence = str(item.get("evidence") or "").strip() or "Not present in provided snippets"
        if value:
            out.append(ContactLead(kind=kind, value=value, evidence=evidence))
    return out[:8]


def _brief_from_data(data: dict) -> LeadBrief | None:
    summary = str(data.get("executive_summary") or "").strip()
    age_sig = str(data.get("company_age_signal") or "").strip()
    hypotheses = [str(x).strip() for x in (data.get("hypotheses") or []) if str(x).strip()]
    questions = [str(x).strip() for x in (data.get("discovery_questions") or []) if str(x).strip()]
    talking = [str(x).strip() for x in (data.get("talking_points") or []) if str(x).strip()]
    contacts = _parse_contacts(data.get("contact_leads"))
    if not summary and not hypotheses and not questions and not talking:
        return None
    return LeadBrief(
        executive_summary=summary or "_Brief sections were empty—re-run or check model output._",
        company_age_signal=age_sig,
        hypotheses=hypotheses,
        discovery_questions=questions,
        talking_points=talking,
        contact_leads=contacts,
    )


def synthesize_brief(
    company: str,
    sources: list[Source],
    extra_context: str | None,
    *,
    locality: str | None = None,
    industry: str | None = None,
) -> LeadBrief:
    model = get_model()

    blocks: list[str] = [
        f"Startup / company: {company}",
        "Task: produce the json brief described in the system message.",
        "",
    ]
    if (locality or "").strip():
        blocks.append(f"Area: {locality.strip()}\n")
    if (industry or "").strip():
        blocks.append(f"Industry hint: {industry.strip()}\n")
    if extra_context:
        blocks.extend(["Notes from user:", extra_context.strip(), ""])
    blocks.append("Snippets:")
    if not sources:
        blocks.append("(none)")
    else:
        for i, s in enumerate(sources[:18], start=1):
            excerpt = (s.excerpt[:700] if s.excerpt else "").replace("\n", " ")
            blocks.append(f'{i}. {s.title}\n   {s.url}\n   "{excerpt}"')

    data = chat_json_object(
        system=_SYSTEM,
        user="\n".join(blocks),
        temperature=0.25,
        model=model,
    )
    brief = _brief_from_data(data)
    if brief is None:
        raise ValueError("LLM returned an empty json brief (no usable fields).")
    return brief
