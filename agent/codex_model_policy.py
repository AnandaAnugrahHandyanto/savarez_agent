"""Codex Plan model-routing policy for Hermes.

The policy is intentionally small and data-only: it keeps gpt-5.5 as the
primary coding/reasoning model while routing auxiliary, monitoring, and cheap
background work to gpt-5.4-mini.  It does not use the direct OpenAI API; callers
that act on this policy should pair it with provider='openai-codex'.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping

CODEX_PROVIDER = "openai-codex"
CODEX_PRIMARY_MODEL = "gpt-5.5"
CODEX_AUX_MODEL = "gpt-5.4-mini"
CODEX_CODING_FALLBACK_MODEL = "gpt-5.3-codex"

_HEAVY_TASK_HINTS = (
    "coding",
    "implementation",
    "code-review",
    "review",
    "debugging",
    "architecture",
    "planning",
    "security",
)
_AUX_TASK_HINTS = (
    "title",
    "summary",
    "summarization",
    "compression",
    "triage",
    "monitor",
    "smoke",
    "classification",
    "metadata",
    "routing",
)


@dataclass(frozen=True)
class CodexRoute:
    provider: str
    model: str
    role: str
    reason: str

    def asdict(self) -> dict[str, str]:
        return asdict(self)


def _normalize_task(task: str | None) -> str:
    return (task or "").strip().lower().replace("_", "-")


def choose_codex_model(task: str | None = None, *, budget: str | None = None, critical: bool = False) -> CodexRoute:
    """Choose the Codex Plan model for a Hermes task.

    Rules:
    - critical or heavy coding/reasoning work -> gpt-5.5
    - auxiliary/background/monitoring/classification work -> gpt-5.4-mini
    - low budget -> gpt-5.4-mini unless critical
    - default -> gpt-5.5, because Hermes' main agent quality matters more than
      shaving small amounts of Codex quota.
    """
    task_norm = _normalize_task(task)
    budget_norm = (budget or "").strip().lower()

    if critical:
        return CodexRoute(CODEX_PROVIDER, CODEX_PRIMARY_MODEL, "primary", "critical task uses primary model")

    if budget_norm in {"low", "cheap", "conserve"}:
        return CodexRoute(CODEX_PROVIDER, CODEX_AUX_MODEL, "auxiliary", "low-budget task uses auxiliary model")

    if any(hint in task_norm for hint in _AUX_TASK_HINTS):
        return CodexRoute(CODEX_PROVIDER, CODEX_AUX_MODEL, "auxiliary", "auxiliary/background task")

    if any(hint in task_norm for hint in _HEAVY_TASK_HINTS):
        return CodexRoute(CODEX_PROVIDER, CODEX_PRIMARY_MODEL, "primary", "coding/reasoning task uses primary model")

    return CodexRoute(CODEX_PROVIDER, CODEX_PRIMARY_MODEL, "primary", "default Hermes task uses primary model")


def codex_policy_payload() -> dict[str, Any]:
    """Return a machine-readable snapshot for diagnostics/docs."""
    return {
        "provider": CODEX_PROVIDER,
        "primary_model": CODEX_PRIMARY_MODEL,
        "auxiliary_model": CODEX_AUX_MODEL,
        "coding_fallback_model": CODEX_CODING_FALLBACK_MODEL,
        "routing_examples": {
            "implementation": choose_codex_model("implementation").asdict(),
            "compression": choose_codex_model("compression").asdict(),
            "codex-monitor": choose_codex_model("codex-monitor").asdict(),
            "urgent-debugging": choose_codex_model("debugging", critical=True).asdict(),
        },
    }


def apply_codex_policy(config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a copy of a Hermes-like config with Codex policy defaults filled.

    Existing explicit values win. This helper is useful for diagnostics and
    future config writers without mutating live config from import-time code.
    """
    result: dict[str, Any] = dict(config or {})
    model_cfg = dict(result.get("model") or {})
    model_cfg.setdefault("provider", CODEX_PROVIDER)
    model_cfg.setdefault("model", CODEX_PRIMARY_MODEL)
    result["model"] = model_cfg

    auxiliary = dict(result.get("auxiliary") or {})
    for task_name in ("compression", "title", "vision", "session_search"):
        task_cfg = dict(auxiliary.get(task_name) or {})
        task_cfg.setdefault("provider", CODEX_PROVIDER)
        task_cfg.setdefault("model", CODEX_AUX_MODEL)
        auxiliary[task_name] = task_cfg
    result["auxiliary"] = auxiliary
    return result
