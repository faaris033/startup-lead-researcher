from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Source(BaseModel):
    title: str
    url: str
    excerpt: str


class ContactLead(BaseModel):
    kind: str  # phone | email | website | linkedin | other
    value: str
    evidence: str


class LeadBrief(BaseModel):
    executive_summary: str
    company_age_signal: str = ""
    hypotheses: list[str] = Field(default_factory=list)
    discovery_questions: list[str] = Field(default_factory=list)
    talking_points: list[str] = Field(default_factory=list)
    contact_leads: list[ContactLead] = Field(default_factory=list)


class LeadResearchReport(BaseModel):
    company: str
    locality: str | None = None
    industry: str | None = None
    sources: list[Source] = Field(default_factory=list)
    brief: LeadBrief | None = None
    contact_leads: list[ContactLead] = Field(default_factory=list)
    playbook: str | None = Field(default=None)
    notes: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_markdown(self) -> str:
        lines: list[str] = [
            f"# Lead research: {self.company}",
            "",
            f"_Generated (UTC): {self.generated_at:%Y-%m-%d %H:%M}_",
            "",
            "_Target profile: young startup (~1 year old or less when evidence supports it) — "
            "AWS / cloud + software development consulting._",
            "",
        ]
        if self.locality or self.industry:
            parts: list[str] = []
            if self.locality:
                parts.append(f"**Area:** {self.locality}")
            if self.industry:
                parts.append(f"**Industry:** {self.industry}")
            lines.extend(["## Focus", "", " · ".join(parts), ""])

        contacts = self.contact_leads

        lines.extend(["## Outreach (phone / email)", ""])
        lines.append(
            "_Only use values that appeared in web snippets. Verify before cold outreach._",
        )
        lines.append("")
        if contacts:
            for c in contacts:
                kind = (c.kind or "other").strip().title()
                val = (c.value or "").strip() or "_Not found_"
                lines.append(f"- **{kind}:** {val}")
                lines.append(f"  - _Source:_ {c.evidence.strip()}")
                lines.append("")
        else:
            lines.append("_No phone or email found in snippets — check company website in Sources._")
            lines.append("")

        if self.notes:
            lines.extend(["## Notes", "", self.notes, ""])
        if self.brief:
            if self.brief.company_age_signal:
                lines.extend(
                    [
                        "## Startup age (from snippets)",
                        "",
                        self.brief.company_age_signal,
                        "",
                    ],
                )
            lines.append("## Executive summary")
            lines.append("")
            lines.append(self.brief.executive_summary or "_Empty._")
            lines.append("")
            if self.brief.hypotheses:
                lines.extend(["## Hypotheses", "", *[f"- {h}" for h in self.brief.hypotheses], ""])
            if self.brief.discovery_questions:
                lines.extend(
                    ["## Discovery questions", "", *[f"- {q}" for q in self.brief.discovery_questions], ""],
                )
            if self.brief.talking_points:
                lines.extend(
                    [
                        "## Talking points (AWS, cloud & dev consulting)",
                        "",
                        *[f"- {t}" for t in self.brief.talking_points],
                        "",
                    ],
                )
        if self.playbook:
            lines.extend([self.playbook.strip(), ""])
        lines.extend(["## Sources", ""])
        if not self.sources:
            lines.append("_No web results. Try different spelling or add `--city` / `--context`._")
        else:
            for i, s in enumerate(self.sources, start=1):
                lines.extend(
                    [
                        f"{i}. [{s.title}]({s.url})",
                        "",
                        f"   {s.excerpt}",
                        "",
                    ],
                )
        return "\n".join(lines).rstrip() + "\n"

    def model_dump_json_pretty(self) -> str:
        data: dict[str, Any] = self.model_dump(mode="json")
        import json

        return json.dumps(data, indent=2, ensure_ascii=False)
