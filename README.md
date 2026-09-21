# Consulting Lead Researcher

Python CLI that researches **early-stage prospects** for AWS / cloud consulting outreach.

Uses **web search** to find companies, then an **LLM via Amazon Bedrock** (OpenAI-compatible API) to:

1. **Select** a company from search results  
2. **Generate structured discovery briefs** — pain hypotheses, discovery questions, and talking points  
3. Apply **prompt-level guardrails** against fabricated contact details  
4. Fall back to a **keyword heuristic** when the model is unavailable  

Excel / CSV export for outbound workflows. This is **not** the Upwork job scanner.

## Features

- Named-company research or auto-discover by area / vertical  
- Amazon Bedrock (or OpenAI) synthesis of discovery briefs  
- Contact extraction with anti-hallucination rules + website fallback  
- Keyword heuristic pick when LLM is down (`--no-pick-llm` / outage path)  
- Append rows to `leads.xlsx` (optional Teams/OneDrive path via `LEADS_XLSX_PATH`)

## Setup

```powershell
cd C:\Users\Faari\upwork_lead_researcher
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
# Set OPENAI_API_KEY + OPENAI_BASE_URL for Bedrock (or OpenAI)
```

## Commands

```powershell
# Health check
.\.venv\Scripts\python.exe -m src.main doctor

# Research a named company
.\.venv\Scripts\python.exe -m src.main research "Acme Inc" --city "Virginia" --industry startup

# Auto-discover one startup + append to Excel
.\.venv\Scripts\python.exe -m src.main research-discover --area "Virginia" --vertical startup --variety

# Sources only (no LLM brief)
.\.venv\Scripts\python.exe -m src.main research "Acme Inc" --no-llm
```

## How AI is used here

| Step | What runs |
|------|-----------|
| Discovery | Web search (not an LLM) |
| Company pick | Bedrock/OpenAI JSON pick, or **keyword heuristic fallback** |
| Brief | Bedrock/OpenAI → hypotheses, discovery questions, talking points |
| Contacts | Prompt rules: never invent phones/emails; omit if unsure |

## Related (separate product)

The **serverless Upwork lead scanner** (Lambda, EventBridge, S3, SNS, CloudFront) is a different repo:  
[`NOVA-Upwork-Scanner`](https://github.com/gonovacloud/NOVA-Upwork-Scanner) — Upwork API + rule-based scoring, **no Bedrock** for finding jobs.

## Secrets (never commit)

- `.env` — Bedrock / OpenAI keys  
- `leads.csv` / `leads.xlsx` — your lead data  

Use `.env.example` as a template only.

## License

Private / internal use unless you add a license file.
