"""Minimal Anthropic client wrapper for the UCPM file-based test loop.

Why a fresh client and not `agent/anthropic_adapter.py`?
  The upstream adapter is a full OpenAI-style ↔ Anthropic-Messages translator
  designed for the multi-turn agent runtime. It pulls in a large surface
  (extended thinking, tool-use, OAuth, Bedrock, credential pools) that we
  don't need for a deterministic, file-driven SOP procedure call. The right
  long-term home for shared LLM helpers is a future `hermes_agent/llm/`
  module — for now this stays small and focused on what P-01 + P-02 need:
    1. Stable JSON output for classification/triage decisions.
    2. Prompt caching for the SOP + company context (these are large and
       reused across every message in the inbox; we should not re-pay for
       them per call).
    3. A test seam so pytest mocks the Anthropic SDK without touching env.

Default model: `claude-sonnet-4-6` (per project memory). Override via
`ANTHROPIC_MODEL` env var or the `model` kwarg on each call.

Secrets: `ANTHROPIC_API_KEY` is read from the environment. In production
this is supplied by Doppler — never `.env`.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 1024


class AnthropicLike(Protocol):
    """Subset of the Anthropic SDK we depend on. Lets tests pass in fakes."""

    @property
    def messages(self) -> Any: ...  # noqa: D401 — protocol stub


@dataclass
class LlmCall:
    """One call's worth of state — useful for tests/debugging."""

    system_blocks: list[dict[str, Any]]
    user_text: str
    response_text: str
    model: str
    usage: dict[str, Any]


class LlmClient:
    """Thin wrapper around Anthropic Messages API with prompt caching.

    System prompt is structured as multiple blocks so we can place
    `cache_control: {"type": "ephemeral"}` on the long, stable context
    (SOP + company state). The short instruction block at the end is
    *not* cached — it changes per call type (classify vs triage vs draft).
    """

    def __init__(
        self,
        client: Optional[AnthropicLike] = None,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
    ):
        self.model = model
        self._call_count = 0
        if client is not None:
            self._client = client
            return

        # Lazy import — keep this module importable in CI without the SDK.
        try:
            import anthropic  # type: ignore
        except ImportError as exc:  # pragma: no cover — exercised only if SDK missing
            raise RuntimeError(
                "anthropic SDK is not installed; install hermes-agent or "
                "`uv pip install anthropic` to use LlmClient with a real backend."
            ) from exc

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Use Doppler to supply it: "
                "`doppler run -- uv run hermes-ucpm test-property-loop ...`."
            )
        self._client = anthropic.Anthropic(api_key=key)

    @property
    def call_count(self) -> int:
        return self._call_count

    def call_json(
        self,
        cached_context_blocks: list[str],
        instruction: str,
        user_payload: str,
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model: Optional[str] = None,
    ) -> tuple[dict[str, Any], LlmCall]:
        """Call the model and parse a single JSON object from its output.

        Args:
            cached_context_blocks: large, stable context strings (SOP, company
                state). Each becomes a system block with `cache_control` set to
                ephemeral so prompt caching applies.
            instruction: short, per-call-type instruction (NOT cached).
            user_payload: the per-message JSON the model decides on.
            max_tokens: cap on response length.
            model: override the default model for this call.
        """
        system_blocks: list[dict[str, Any]] = []
        for block in cached_context_blocks:
            if not block:
                continue
            system_blocks.append(
                {
                    "type": "text",
                    "text": block,
                    "cache_control": {"type": "ephemeral"},
                }
            )
        # Final per-call instruction is intentionally uncached — it is short
        # and varies between classify/triage/draft.
        system_blocks.append({"type": "text", "text": instruction})

        chosen_model = model or self.model
        response = self._client.messages.create(
            model=chosen_model,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": user_payload}],
        )
        self._call_count += 1

        text = _extract_text(response)
        parsed = _parse_json_block(text)
        usage = _extract_usage(response)

        return parsed, LlmCall(
            system_blocks=system_blocks,
            user_text=user_payload,
            response_text=text,
            model=chosen_model,
            usage=usage,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_text(response: Any) -> str:
    """Pull the assistant text out of an Anthropic Messages response.

    Tolerates both real SDK responses and dict-shaped fakes used in tests.
    """
    content = getattr(response, "content", None)
    if content is None and isinstance(response, dict):
        content = response.get("content")
    if not content:
        raise ValueError("Anthropic response had no content")

    # SDK form: list of content blocks each with `.text`
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text:
            parts.append(text)
    if not parts:
        raise ValueError("Anthropic response content had no text blocks")
    return "\n".join(parts)


def _parse_json_block(text: str) -> dict[str, Any]:
    """Parse a JSON object out of the model's response.

    Allows either pure JSON or JSON inside a fenced code block. Errors here
    surface as a hard failure — the loop must not silently misclassify.
    """
    candidate = text.strip()
    # Strip ```json ... ``` fencing if present.
    if candidate.startswith("```"):
        first_newline = candidate.find("\n")
        if first_newline != -1:
            candidate = candidate[first_newline + 1 :]
        if candidate.endswith("```"):
            candidate = candidate[: -len("```")].rstrip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned non-JSON response: {text[:500]!r}"
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"LLM returned JSON of type {type(parsed).__name__}, expected object"
        )
    return parsed


def _extract_usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    # SDK Usage object — pull the standard fields if present.
    out: dict[str, Any] = {}
    for field in (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    ):
        value = getattr(usage, field, None)
        if value is not None:
            out[field] = value
    return out
