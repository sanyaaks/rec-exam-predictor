"""Thin, optional wrapper around the Claude API.

Used only for study material (answers / outlines). Extraction, classification,
matching and scoring are deterministic and run without any API key.
"""
from __future__ import annotations

import logging

from ..config import ANTHROPIC_MODEL, LLM_ENABLED

log = logging.getLogger(__name__)
_client = None


def enabled() -> bool:
    return LLM_ENABLED


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    return _client


def complete(system: str, prompt: str, max_tokens: int = 16000) -> str | None:
    """Return the model's text, or None if the LLM is unavailable or declined."""
    if not LLM_ENABLED:
        return None
    import anthropic

    try:
        resp = _get_client().beta.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.RateLimitError as e:
        log.warning("LLM rate limited: %s", e)
        return None
    except anthropic.APIStatusError as e:
        log.warning("LLM API error %s: %s", e.status_code, e)
        return None
    except anthropic.APIConnectionError as e:
        log.warning("LLM connection error: %s", e)
        return None
    if resp.stop_reason == "refusal":
        return None
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text or None


def complete_json(system: str, prompt: str, schema: dict, max_tokens: int = 8000) -> dict | None:
    """Structured output (JSON schema). Returns the parsed object, or None if unavailable/declined."""
    if not LLM_ENABLED:
        return None
    import json

    import anthropic

    try:
        resp = _get_client().beta.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.RateLimitError as e:
        log.warning("LLM rate limited: %s", e)
        return None
    except anthropic.APIStatusError as e:
        log.warning("LLM API error %s: %s", e.status_code, e)
        return None
    except anthropic.APIConnectionError as e:
        log.warning("LLM connection error: %s", e)
        return None
    if resp.stop_reason in ("refusal", "max_tokens"):
        return None
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
