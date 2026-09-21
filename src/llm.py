"""LLM client — direct OpenAI or OpenAI-compatible Amazon Bedrock endpoint."""

from __future__ import annotations

import json
import os
import re

from openai import OpenAI

_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
_DEFAULT_BEDROCK_MODEL = "openai.gpt-oss-20b-1:0"


def is_bedrock() -> bool:
    provider = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if provider == "bedrock":
        return True
    if provider == "openai":
        return False
    base = (os.environ.get("OPENAI_BASE_URL") or "").lower()
    return "bedrock" in base


def llm_configured() -> bool:
    return bool((os.environ.get("OPENAI_API_KEY") or "").strip())


def llm_provider_label() -> str:
    return "Amazon Bedrock (OpenAI-compatible)" if is_bedrock() else "OpenAI API"


def get_model() -> str:
    explicit = (os.environ.get("OPENAI_MODEL") or "").strip()
    if explicit:
        return explicit
    return _DEFAULT_BEDROCK_MODEL if is_bedrock() else _DEFAULT_OPENAI_MODEL


def get_openai_client() -> OpenAI:
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "No LLM credentials. Set OPENAI_API_KEY "
            "(OpenAI key or Amazon Bedrock API key) in .env."
        )
    base_url = (os.environ.get("OPENAI_BASE_URL") or "").strip().rstrip("/")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    if is_bedrock():
        raise RuntimeError(
            "LLM_PROVIDER=bedrock but OPENAI_BASE_URL is missing. "
            "Example: https://bedrock-mantle.us-east-1.api.aws/v1"
        )
    return OpenAI(api_key=api_key)


def _extract_json_object(raw: str) -> dict:
    text = raw.strip()
    if not text:
        raise ValueError("Model returned empty content.")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    raise ValueError("Model did not return a JSON object.")


def chat_json_object(
    *,
    system: str,
    user: str,
    temperature: float = 0.25,
    model: str | None = None,
) -> dict:
    """Chat completion that must yield a JSON object (brief, business pick, etc.)."""
    client = get_openai_client()
    model_id = (model or get_model()).strip()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    def _call(with_json_mode: bool):
        kwargs: dict = {
            "model": model_id,
            "temperature": temperature,
            "messages": messages,
        }
        if with_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return client.chat.completions.create(**kwargs)

    try:
        resp = _call(with_json_mode=not is_bedrock())
    except Exception:
        resp = _call(with_json_mode=False)

    raw = (resp.choices[0].message.content or "").strip()
    return _extract_json_object(raw)
