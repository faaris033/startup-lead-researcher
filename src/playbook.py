"""Offline checklist when LLM is off — conversation prompts, not facts from the web."""

STARTUP_PLAYBOOK = """## Young startup checklist (AWS + dev consulting)

Use only as **conversation prompts**—validate age and contacts against your sources.

- **Age / stage:** Any signal they launched in the last ~12 months? Accelerator, pre-seed, solo founder?
- **Product:** MVP live or still building? Who wrote the code (founder vs contractor)?
- **Hosting:** Where does the app run today (shared hosting, one VPS, Heroku, nothing yet)?
- **Releases:** How do they deploy—manual FTP, Git push, no CI/CD?
- **AWS fit:** Would RDS + S3 + a small ECS/Lambda slice solve their next milestone without overbuilding?
- **Dev fit:** Do they need a short contract for API, dashboard, or integration work?
- **Contacts:** Use only phone/email from snippets; otherwise find on their site/LinkedIn manually.
"""
