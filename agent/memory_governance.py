"""Governance helpers for automatic memory context injection.

This module sits above memory providers. Providers may return legacy formatted
text via ``prefetch()`` or richer dictionaries via ``prefetch_candidates()``;
Hermes core owns final filtering, reranking, and redaction before context is
injected into the model.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any, Iterable, Mapping

from agent.redact import redact_sensitive_text

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{1,}", re.IGNORECASE)

_STOPWORDS = {
    "about",
    "again",
    "also",
    "could",
    "current",
    "does",
    "give",
    "have",
    "into",
    "know",
    "like",
    "mean",
    "please",
    "remind",
    "should",
    "that",
    "the",
    "their",
    "there",
    "this",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "you",
    "your",
}

_STALE_MARKERS = {
    "stale",
    "superseded",
    "deprecated",
    "obsolete",
    "replaced",
    "inactive",
    "old",
}

_SECRET_MARKERS = {
    "secret",
    "credential",
    "credentials",
    "api-key",
    "api_key",
    "token",
    "password",
}

_GLOBAL_SCOPES = {"", "all", "any", "global", "shared"}


@dataclass(frozen=True)
class GovernedMemoryCandidate:
    """A memory item after normalization and before/after governance."""

    content: str
    provider: str = ""
    trust: float = 0.0
    metadata: Mapping[str, Any] | None = None


def active_profile_scope() -> str:
    """Return the active profile identity used for scope filtering."""
    for key in ("HERMES_PROFILE", "HERMES_AGENT_IDENTITY", "HERMES_PROFILE_NAME"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return "default"


def query_tokens(query: str) -> set[str]:
    """Normalize a natural-language user message into recall tokens."""
    tokens = {m.group(0).lower().strip("_-") for m in _TOKEN_RE.finditer(query or "")}
    return {t for t in tokens if t and t not in _STOPWORDS and len(t) > 2}


def normalize_candidates(raw: Iterable[Any], *, provider: str = "") -> list[GovernedMemoryCandidate]:
    """Convert provider-returned candidate dicts/strings into candidates."""
    candidates: list[GovernedMemoryCandidate] = []
    for item in raw or []:
        if isinstance(item, str):
            content = item.strip()
            if content:
                candidates.append(GovernedMemoryCandidate(content=content, provider=provider))
            continue
        if not isinstance(item, Mapping):
            continue
        content = str(item.get("content") or item.get("text") or item.get("memory") or "").strip()
        if not content:
            continue
        trust = item.get("trust_score", item.get("trust", item.get("score", 0.0)))
        try:
            trust_f = float(trust or 0.0)
        except (TypeError, ValueError):
            trust_f = 0.0
        candidates.append(
            GovernedMemoryCandidate(
                content=content,
                provider=str(item.get("provider") or provider or ""),
                trust=trust_f,
                metadata=dict(item),
            )
        )
    return candidates


def govern_candidates(
    candidates: Iterable[GovernedMemoryCandidate],
    query: str,
    *,
    profile: str | None = None,
    limit: int = 5,
) -> list[GovernedMemoryCandidate]:
    """Filter, redact, and rerank memory candidates for context injection."""
    q_tokens = query_tokens(query)
    profile = (profile or active_profile_scope() or "default").strip().lower()
    governed: list[tuple[float, GovernedMemoryCandidate]] = []

    for cand in candidates:
        meta = dict(cand.metadata or {})
        if _is_wrong_scope(meta, profile):
            continue
        if _is_stale(meta):
            continue
        if _has_secret_marker(meta):
            continue

        redacted = redact_sensitive_text(cand.content, force=True)
        if redacted != cand.content:
            # Automatic memory injection is not the right place to surface even
            # redacted credentials; omit the whole candidate to avoid teaching
            # the model that a secret exists.
            continue

        overlap = len(q_tokens & query_tokens(cand.content))
        if q_tokens and overlap == 0:
            continue
        score = float(overlap) * 10.0 + max(cand.trust, 0.0)
        governed.append((score, cand))

    governed.sort(key=lambda pair: pair[0], reverse=True)
    return [cand for _, cand in governed[: max(0, int(limit))]]


def render_governed_context(provider_name: str, candidates: Iterable[GovernedMemoryCandidate]) -> str:
    """Render governed candidates in the legacy text context format."""
    lines = []
    for cand in candidates:
        if cand.trust:
            lines.append(f"- [{cand.trust:.1f}] {cand.content}")
        else:
            lines.append(f"- {cand.content}")
    if not lines:
        return ""
    label = provider_name.replace("_", " ").replace("-", " ").title() if provider_name else "Memory"
    return f"## {label} Memory\n" + "\n".join(lines)


def sanitize_legacy_context(text: str) -> str:
    """Best-effort governance for legacy provider text."""
    text = redact_sensitive_text(text or "", force=True)
    kept = []
    for line in text.splitlines():
        if not line.strip():
            kept.append(line)
            continue
        lowered = line.lower()
        if any(marker in lowered for marker in _SECRET_MARKERS):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _metadata_words(meta: Mapping[str, Any], keys: tuple[str, ...]) -> set[str]:
    words: set[str] = set()
    for key in keys:
        value = meta.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            parts = value
        else:
            parts = re.split(r"[,\s]+", str(value))
        words.update(str(part).strip().lower() for part in parts if str(part).strip())
    return words


def _is_wrong_scope(meta: Mapping[str, Any], profile: str) -> bool:
    scopes = _metadata_words(meta, ("profile", "profile_scope", "scope", "agent_identity"))
    if not scopes:
        return False
    return not any(scope in _GLOBAL_SCOPES or scope == profile for scope in scopes)


def _is_stale(meta: Mapping[str, Any]) -> bool:
    words = _metadata_words(meta, ("status", "state", "tags", "tag"))
    if words & _STALE_MARKERS:
        return True
    for key in ("stale", "superseded", "deprecated", "obsolete"):
        value = meta.get(key)
        if isinstance(value, bool) and value:
            return True
    return False


def _has_secret_marker(meta: Mapping[str, Any]) -> bool:
    return bool(_metadata_words(meta, ("tags", "tag", "category", "kind")) & _SECRET_MARKERS)
