from __future__ import annotations

import os

from src.contacts import (
    curate_contact_leads,
    enrich_contact_leads,
    extract_contacts_from_sources,
    merge_contact_leads,
)
from src.discovery import merge_source_lists, search_contact_signals, search_public_signals
from src.llm import llm_configured
from src.playbook import STARTUP_PLAYBOOK
from src.schemas import LeadResearchReport
from src.synthesis import synthesize_brief


def run_lead_research(
    company: str,
    *,
    locality: str | None = None,
    industry: str | None = None,
    extra_context: str | None = None,
    use_llm: bool = True,
) -> LeadResearchReport:
    name = company.strip()
    loc = (locality or "").strip() or None
    ind = (industry or "").strip() or None

    if not name:
        return LeadResearchReport(
            company="(empty)",
            locality=loc,
            industry=ind,
            sources=[],
            brief=None,
            notes="Provide a non-empty company or startup name.",
        )

    general = search_public_signals(name, locality=loc, industry=ind)
    contact_hits = search_contact_signals(name, locality=loc)
    sources = merge_source_lists(general, contact_hits, max_total=32)
    regex_contacts = extract_contacts_from_sources(sources, company=name)
    notes: list[str] = []
    if not sources:
        notes.append("Web discovery returned no snippets (try alternate spelling, different city, or check network).")

    brief = None
    if not use_llm:
        notes.append("LLM synthesis disabled; sources only.")
    elif not llm_configured():
        notes.append(
            "Set OPENAI_API_KEY (OpenAI or Bedrock API key) and OPENAI_BASE_URL for Bedrock "
            "to enable startup brief + contact extraction from snippets."
        )
    else:
        try:
            brief = synthesize_brief(
                name,
                sources,
                extra_context,
                locality=loc,
                industry=ind,
            )
        except Exception as exc:  # noqa: BLE001 — surface to operator
            notes.append(f"LLM synthesis failed: {exc}")

    llm_contacts = brief.contact_leads if brief else []
    all_contacts = merge_contact_leads(regex_contacts, llm_contacts)
    all_contacts = curate_contact_leads(all_contacts, company=name)
    all_contacts = enrich_contact_leads(all_contacts, sources, company=name)
    if not all_contacts and sources:
        notes.append(
            "No phone/email found in snippets—check the company site or LinkedIn manually before outreach.",
        )

    playbook: str | None = STARTUP_PLAYBOOK if brief is None else None

    return LeadResearchReport(
        company=name,
        locality=loc,
        industry=ind,
        sources=sources,
        brief=brief,
        contact_leads=all_contacts,
        playbook=playbook,
        notes=" ".join(notes) if notes else None,
    )
