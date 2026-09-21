from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import typer

from src.auto_discover import parse_exclude_list, pick_business_name
from src.discovery import search_vertical_in_area
from src.env_bootstrap import PROJECT_ROOT, bootstrap_env
from src.llm import get_model, llm_configured, llm_provider_label
from src.export import (
    append_report_to_csv,
    append_report_to_xlsx,
    count_csv_data_rows,
    count_xlsx_data_rows,
    read_companies_from_spreadsheet,
    resolve_csv_path,
    resolve_xlsx_path,
)
from src.pipeline import run_lead_research
from src.schemas import LeadResearchReport

bootstrap_env()


def _say(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _write_outputs(
    report: LeadResearchReport,
    *,
    json_out: Path | None,
    xlsx_out: Path | None,
    csv_out: Path | None,
    overwrite: bool,
    no_xlsx: bool,
    no_csv: bool,
    also_csv: bool,
) -> None:
    if json_out:
        json_out.write_text(report.model_dump_json_pretty(), encoding="utf-8")
        _say(f"Wrote JSON: {json_out.resolve()}")

    primary: Path | None = None
    rows = 0

    if not no_xlsx:
        xlsx_path = resolve_xlsx_path(xlsx_out)
        try:
            append_report_to_xlsx(report, xlsx_path, append=not overwrite)
            rows = count_xlsx_data_rows(xlsx_path)
            primary = xlsx_path
            action = "Replaced" if overwrite else "Appended to"
            _say(f"{action} Excel workbook: {xlsx_path} ({rows} row(s))")
        except RuntimeError as exc:
            _say(str(exc))
            if no_csv and not also_csv:
                _say("Falling back to leads.csv — run: pip install openpyxl")
                also_csv = True

    write_csv = (no_xlsx or also_csv or not no_csv) and not (no_xlsx and no_csv)
    if primary is None:
        write_csv = True
    if write_csv and not no_csv:
        csv_path = resolve_csv_path(csv_out)
        append_report_to_csv(report, csv_path, append=not overwrite)
        if primary is None:
            primary = csv_path
            rows = count_csv_data_rows(csv_path)
            _say(f"Saved CSV: {csv_path} ({rows} row(s))")

    if primary:
        typer.echo("")
        typer.echo("---")
        typer.echo(f"**Spreadsheet:** {primary}")
        typer.echo(f"**Data rows:** {rows}")
        typer.echo("")
        typer.echo(
            "Keep using this **.xlsx** file for formatting. "
            "The tool appends new rows without replacing your header row.",
        )
        if also_csv:
            typer.echo(f"CSV copy also updated: {resolve_csv_path(csv_out)}")
        typer.echo("---")
        typer.echo("")


app = typer.Typer(
    no_args_is_help=True,
    help="Young-startup lead research — AWS/cloud consulting briefs via Bedrock/OpenAI.",
)


@app.command()
def version() -> None:
    typer.echo("consulting-lead-research 0.7.0 (lead research only — Upwork scanner is a separate repo)")


@app.command()
def doctor() -> None:
    """Quick checks when the CLI prints nothing or hangs — run this first."""
    root = Path(__file__).resolve().parents[1]
    py = sys.executable
    typer.echo(f"Python: {py}")
    typer.echo(f"Project root: {root}")
    typer.echo(f".env exists: {(root / '.env').exists()}")
    typer.echo(f"LLM provider: {llm_provider_label()}")
    typer.echo(f"LLM configured: {llm_configured()}")
    typer.echo(f"OPENAI_BASE_URL: {os.environ.get('OPENAI_BASE_URL') or '(default OpenAI API)'}")
    typer.echo(f"OPENAI_MODEL: {get_model()}")
    typer.echo("Imports: typer, ddgs, openai:", nl=False)
    try:
        import ddgs as _dg  # noqa: F401
        import openai  # noqa: F401
        import typer as _tp  # noqa: F401

        typer.echo(" ok")
    except Exception as exc:
        typer.echo(f" FAIL ({exc})")
        raise typer.Exit(code=1) from exc
    typer.echo("")
    typer.echo("Tip: web search often takes 15–45s; research commands print progress to stderr.")
    typer.echo("If stdout looks frozen, use: python -u -m src.main research Acme --no-llm")
    from src.export import default_xlsx_path

    xlsx = default_xlsx_path()
    csv = PROJECT_ROOT / "leads.csv"
    typer.echo(f"Excel workbook: {xlsx} (exists: {xlsx.exists()})")
    if os.environ.get("LEADS_XLSX_PATH"):
        typer.echo("(from LEADS_XLSX_PATH in .env)")
    typer.echo(f"Optional CSV copy: {csv} (exists: {csv.exists()})")
    try:
        import openpyxl  # noqa: F401

        typer.echo("openpyxl: ok (Excel append enabled)")
    except ImportError:
        typer.echo("openpyxl: missing — run .venv\\Scripts\\pip install openpyxl")


@app.command()
def research(
    company: str = typer.Argument(..., help="Business name to research"),
    city: str | None = typer.Option(
        None,
        "--city",
        help="City or region (local SMB mode when set)",
    ),
    industry: str | None = typer.Option(
        None,
        "--industry",
        "-i",
        help="Business type, e.g. dental, restaurant",
    ),
    context: str | None = typer.Option(
        None,
        "--context",
        "-c",
        help="Extra notes for the brief",
    ),
    json_out: Path | None = typer.Option(
        None,
        "--json-out",
        help="Write JSON report to this path",
    ),
    xlsx_out: Path | None = typer.Option(
        None,
        "--xlsx-out",
        help="Excel workbook path (default: leads.xlsx in project folder)",
    ),
    csv_out: Path | None = typer.Option(
        None,
        "--csv-out",
        help="Optional CSV path (only with --also-csv unless --no-xlsx)",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Replace data rows instead of appending (keeps header row in .xlsx)",
    ),
    no_xlsx: bool = typer.Option(False, "--no-xlsx", help="Do not update leads.xlsx (CSV only)"),
    also_csv: bool = typer.Option(False, "--also-csv", help="Also update leads.csv (in addition to .xlsx)"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Web sources only (no LLM brief)"),
) -> None:
    _say("Searching the web + contact pages… (often 20–60s — wait for the report below)")
    report = run_lead_research(
        company,
        locality=city,
        industry=industry,
        extra_context=context,
        use_llm=not no_llm,
    )
    typer.echo(report.to_markdown())
    _write_outputs(
        report,
        json_out=json_out,
        xlsx_out=xlsx_out,
        csv_out=csv_out,
        overwrite=overwrite,
        no_xlsx=no_xlsx,
        no_csv=not also_csv,
        also_csv=also_csv,
    )


@app.command()
def research_discover(
    area: str = typer.Option(
        ...,
        "--area",
        "-a",
        help='Region, e.g. "Bloomingdale, IL" or "Loudoun County, VA"',
    ),
    vertical: str = typer.Option(
        "startup",
        "--vertical",
        "-v",
        help="Startup sector or keyword, e.g. fintech, healthtech, SaaS",
    ),
    context: str | None = typer.Option(None, "--context", "-c", help="Extra notes for the brief"),
    json_out: Path | None = typer.Option(None, "--json-out", help="Write JSON report to this path"),
    xlsx_out: Path | None = typer.Option(
        None,
        "--xlsx-out",
        help="Excel workbook path (default: leads.xlsx in project folder)",
    ),
    csv_out: Path | None = typer.Option(None, "--csv-out", help="Optional CSV path (with --also-csv)"),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Replace data rows instead of appending (keeps header row in .xlsx)",
    ),
    no_xlsx: bool = typer.Option(False, "--no-xlsx", help="Do not update leads.xlsx (CSV only)"),
    also_csv: bool = typer.Option(False, "--also-csv", help="Also update leads.csv"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Web sources only for the final report"),
    no_pick_llm: bool = typer.Option(
        False,
        "--no-pick-llm",
        help="Pick business name from titles only (no LLM for the pick)",
    ),
    variety: bool = typer.Option(False, "--variety", help="Shuffle / rotate queries for varied picks"),
    exclude: list[str] = typer.Option(
        [],
        "--exclude",
        "-x",
        help="Skip names containing this text (repeat flag or comma-separated)",
    ),
    exclude_seen: bool = typer.Option(
        True,
        "--exclude-seen/--no-exclude-seen",
        help="Skip companies already in leads.xlsx / leads.csv (default: on)",
    ),
) -> None:
    """Search area for young startups (~1y), pick one, run full research report with contacts."""
    qv = random.randint(0, 3)
    _say(f"Searching “{vertical}” in “{area}”… (15–45s is normal)")
    candidates = search_vertical_in_area(vertical, area, query_variant=qv)
    if not candidates:
        typer.echo("No search results; try broader --area or --vertical wording.", err=True)
        raise typer.Exit(code=1)

    exclude_needles = parse_exclude_list(*exclude)
    if exclude_seen:
        seen = read_companies_from_spreadsheet(xlsx_path=xlsx_out, csv_path=csv_out)
        exclude_needles = parse_exclude_list(*exclude, *seen)
        if seen:
            _say(
                f"Skipping {len(seen)} company/companies already in spreadsheet: {', '.join(seen[:5])}"
                + ("…" if len(seen) > 5 else ""),
            )

    use_pick_llm = not no_pick_llm and llm_configured()
    if use_pick_llm:
        _say("Choosing a business with LLM…")
    else:
        _say("Choosing a business from search titles…")
    name, how = pick_business_name(
        candidates,
        vertical=vertical,
        area=area,
        use_llm=use_pick_llm,
        exclude=exclude_needles,
        variety=variety,
    )

    typer.echo(f"## Auto-selected business\n\n**{name}**\n\n_{how}_\n\n---\n\n")

    if not no_llm and llm_configured():
        _say(f"Building full brief for «{name}»…")
    elif not no_llm:
        _say("Skipping LLM brief (no API key — web + checklist only)")
    else:
        _say(f"Fetching web sources + contact search for «{name}»…")
    report = run_lead_research(
        name,
        locality=area,
        industry=vertical,
        extra_context=context,
        use_llm=not no_llm,
    )
    typer.echo(report.to_markdown())
    _write_outputs(
        report,
        json_out=json_out,
        xlsx_out=xlsx_out,
        csv_out=csv_out,
        overwrite=overwrite,
        no_xlsx=no_xlsx,
        no_csv=not also_csv,
        also_csv=also_csv,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
