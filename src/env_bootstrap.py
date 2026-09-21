"""Load .env from the project root (not cwd) and normalize common copy/paste issues."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _clean_api_key(raw: str) -> str:
    """Strip quotes, BOM, and any whitespace/newlines that break Authorization headers."""
    s = raw.strip().strip('"').strip("'")
    s = s.removeprefix("\ufeff")
    s = "".join(s.split())
    return s


def bootstrap_env() -> Path:
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    raw = os.environ.get("OPENAI_API_KEY")
    if raw is not None:
        cleaned = _clean_api_key(raw)
        if cleaned:
            os.environ["OPENAI_API_KEY"] = cleaned
        else:
            os.environ.pop("OPENAI_API_KEY", None)
    base = os.environ.get("OPENAI_BASE_URL")
    if base is not None:
        cleaned_base = base.strip().strip('"').strip("'").rstrip("/")
        if cleaned_base:
            os.environ["OPENAI_BASE_URL"] = cleaned_base
        else:
            os.environ.pop("OPENAI_BASE_URL", None)
    return PROJECT_ROOT
