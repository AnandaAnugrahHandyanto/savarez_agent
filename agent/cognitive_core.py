"""Darwin/Hermes Cognitive Core policy layer.

This module is intentionally deterministic and side-effect free.  It does not
execute tools, read external services, write memory, or mutate runtime state; it
only builds prompt guidance and a compact per-turn routing hint for AIAgent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
import re
import shutil
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
DEFAULT_MODE = "contextual"
COGNITIVE_CORE_MARKER = "# Hermes Cognitive Core"


@dataclass(frozen=True)
class CognitiveRoute:
    """Stable, serialisable output from the deterministic router."""

    selected_mode: str
    confidence: float
    trigger_evidence: List[str] = field(default_factory=list)
    secondary_modes: List[str] = field(default_factory=list)
    approval_required: bool = False
    requires_clarification: bool = False
    required_checks: List[str] = field(default_factory=list)
    degradation_messages: List[str] = field(default_factory=list)
    fallback_status: str = "matched"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_MODE_ORDER = [
    "external_capability",
    "health",
    "technical",
    "epistemological",
    "contextual",
]

_PATTERNS: Dict[str, Sequence[tuple[str, str]]] = {
    "technical": (
        (r"\b(code|codigo|código|program|debug|bug|test|pytest|repo|git|api|sql|docker|nats|infra|deploy|runtime|router|arquitectura|config|herramienta|tool)\b", "technical keyword"),
        (r"\b(implementar|refactor|auditar|compilar|instalar|automatizar)\b", "technical action"),
    ),
    "epistemological": (
        (r"\b(idea|supuesto|sesgo|contradicci[oó]n|hip[oó]tesis|filosof|argumento|marco conceptual|criterio|inferencial|epistem)\b", "epistemic keyword"),
        (r"\b(analiza|cuestiona|tensiona|critica|crítica|confronta|por qu[eé])\b", "critical analysis request"),
    ),
    "health": (
        (r"\b(salud|health|m[eé]dico|laboratorio|an[aá]lisis de sangre|s[ií]ntoma|diagn[oó]stico|medicaci[oó]n|dosis|presi[oó]n|glucosa|colesterol|sue[nñ]o|peso|dolor)\b", "health keyword"),
    ),
    "contextual": (
        (r"\b(record[aá]|memoria|honcho|obsidian|daily|hist[oó]rico|contexto|antes|pasado|conexi[oó]n|patr[oó]n|recurrencia)\b", "context keyword"),
    ),
    "external_capability": (
        (r"\b(email|mail|correo|gmail|calendar|calendario|nota|obsidian|telegram|mensaje|manda(le)?|enviar|publica|webhook|nats|agent\.bus|recordatorio)\b", "external capability keyword"),
        (r"\b(crea|crear|modifica|actualiza|borra|elimina|manda|env[ií]a|publica|agenda)\b", "external/write verb"),
    ),
}

_WRITE_OR_EXTERNAL_ACTION = re.compile(
    r"\b(crea|crear|modifica|actualiza|borra|elimina|manda|mandale|env[ií]a|enviale|publica|agenda|restart|reinicia|deploy|push|merge)\b",
    re.IGNORECASE,
)
_HEALTH_FALSE_POSITIVES = (
    "salud del sistema",
    "health check",
    "local health",
    "system health",
)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _flag_value(raw: Any) -> Optional[bool]:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return None


def get_cognitive_core_config(config: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    agent_cfg = _as_mapping(_as_mapping(config).get("agent"))
    return _as_mapping(agent_cfg.get("cognitive_core"))


def is_cognitive_core_enabled(config: Optional[Mapping[str, Any]] = None) -> bool:
    """Return whether Cognitive Core should be active.

    Env var is an explicit override; config defaults to disabled for upstream-safe
    rollout.  Darwin Local can enable it via config.yaml.
    """

    env = _flag_value(os.getenv("HERMES_COGNITIVE_CORE"))
    if env is not None:
        return env
    cc_cfg = get_cognitive_core_config(config)
    return bool(_flag_value(cc_cfg.get("enabled")) or False)


def _score_patterns(text: str) -> Dict[str, List[str]]:
    evidence: Dict[str, List[str]] = {mode: [] for mode in _MODE_ORDER}
    for mode, patterns in _PATTERNS.items():
        for pattern, label in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                evidence[mode].append(label)
    return evidence


def route_message(message: str) -> CognitiveRoute:
    """Route a user message to a cognitive mode without LLM calls or side effects."""

    text = (message or "").strip()
    lowered = text.lower()
    evidence_by_mode = _score_patterns(lowered)

    if evidence_by_mode["health"] and any(fp in lowered for fp in _HEALTH_FALSE_POSITIVES):
        evidence_by_mode["health"] = []
        evidence_by_mode["technical"].append("health metaphor suppressed")

    scores = {mode: len(evidence_by_mode[mode]) for mode in _MODE_ORDER}
    selected = DEFAULT_MODE
    for mode in _MODE_ORDER:
        if scores[mode] > scores[selected]:
            selected = mode

    if scores[selected] == 0:
        selected = DEFAULT_MODE
        fallback_status = "fallback_default"
        reason = "No strong route matched; using contextual/default mode."
        confidence = 0.45
    else:
        fallback_status = "matched"
        reason = f"Matched {selected} evidence."
        confidence = min(0.95, 0.55 + 0.15 * scores[selected])

    secondaries = [
        mode for mode in _MODE_ORDER
        if mode != selected and scores[mode] > 0
    ][:3]

    approval_required = bool(
        selected == "external_capability" and _WRITE_OR_EXTERNAL_ACTION.search(lowered)
    )
    required_checks: List[str] = []
    if selected == "technical":
        required_checks.extend(["inspect relevant files/state", "verify with tests or smoke checks"])
    if selected == "health":
        required_checks.extend(["preserve temporal evidence", "avoid diagnosis without clinician-grade evidence"])
    if selected == "contextual":
        required_checks.append("search durable memory when cross-session context is relevant")
    if selected == "external_capability":
        required_checks.extend(["read-only by default", "explicit approval before writes/sends"])
    if approval_required:
        required_checks.append("obtain explicit user approval for side effects")

    return CognitiveRoute(
        selected_mode=selected,
        confidence=round(confidence, 2),
        trigger_evidence=evidence_by_mode[selected][:5],
        secondary_modes=secondaries,
        approval_required=approval_required,
        requires_clarification=False,
        required_checks=required_checks,
        degradation_messages=[],
        fallback_status=fallback_status,
        reason=reason,
    )


def detect_mail_readonly_status(valid_tool_names: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Return shape-only status for the mail read-only capability.

    This does not read config contents, authenticate, contact IMAP/SMTP, or list
    messages. It only checks whether a read-only path could be attempted later.
    """

    tools = set(valid_tool_names or [])
    terminal_available = "terminal" in tools or not tools
    himalaya_present = shutil.which("himalaya") is not None
    config_candidates = (
        Path.home() / ".config" / "himalaya" / "config.toml",
        Path.home() / ".config" / "pimalaya" / "himalaya" / "config.toml",
    )
    config_present = any(path.exists() for path in config_candidates)
    if not terminal_available:
        status = "blocked_no_terminal_tool"
    elif not himalaya_present:
        status = "blocked_himalaya_missing"
    elif not config_present:
        status = "blocked_not_configured"
    else:
        status = "ready_readonly_requires_user_request"
    return {
        "status": status,
        "terminal_tool_present": terminal_available,
        "himalaya_present": himalaya_present,
        "config_present": config_present,
        "network_attempted": False,
        "mail_read_attempted": False,
        "write_attempted": False,
    }


def _capability_lines(valid_tool_names: Optional[Iterable[str]]) -> List[str]:
    tools = set(valid_tool_names or [])
    mail_status = detect_mail_readonly_status(tools)
    return [
        "- Obsidian/vault: local file-backed notes; writes require normal file-write discipline and verification.",
        "- Calendar: read-only unless the user explicitly approves a write/create/update operation.",
        "- Mail: read-only capability status: "
        f"{mail_status['status']}. Allowed only when configured: account/folder/envelope listing and message read via safe Himalaya commands. "
        "Forbidden without explicit future write gate: send, reply, forward, mark seen/unseen, flag, move, copy, archive, delete, attachment download, credential setup/OAuth, or config writes.",
        "- NATS/agent.bus: deferred_optional; do not use NATS CLI, publish/subscribe/request/reply, or agent.bus without a future explicit gate.",
        "- Messaging/webhooks: external side effects; require explicit approval and external receipt verification.",
        "- Honcho/session memory: read/query selectively; write only durable facts under the memory policy.",
    ]


def build_cognitive_core_prompt(
    config: Optional[Mapping[str, Any]] = None,
    *,
    valid_tool_names: Optional[Iterable[str]] = None,
) -> str:
    """Build the stable Cognitive Core system prompt block."""

    if not is_cognitive_core_enabled(config):
        return ""

    cc_cfg = get_cognitive_core_config(config)
    name = str(cc_cfg.get("name") or "Hermes Cognitive Core").strip()
    default_style = str(cc_cfg.get("style") or "direct, critical, concise").strip()

    caps = "\n".join(_capability_lines(valid_tool_names))

    return f"""{COGNITIVE_CORE_MARKER}

## Identity
You operate as {name}: one coherent agent with specialized cognitive modes, not multiple personalities. Your goal is to amplify the user's judgment through analysis, serious challenge, assumption detection, alternatives, and critical synthesis. Do not flatter. Do not contradict performatively. When an idea survives analysis, explain why it survives.

Default style: {default_style}.

## Runtime routing
For each user turn, use the hidden Cognitive Core route hint when present. Treat it as advisory routing metadata, not user-visible content. Do not expose internal mode labels unless the user asks.

Modes:
- technical: programming, architecture, debugging, infra, agents, automation, audits. Be precise, operational, and verification-oriented.
- epistemological: concepts, assumptions, bias, logic, frames, philosophy used as serious tension rather than ornament.
- health: medical history, labs, habits, physiological metrics. Be factual, conservative, temporally traceable; do not diagnose or dramatize.
- contextual: historical connections, recurring patterns, contradictions over time, memory consolidation candidates.
- external_capability: tools/services/actions. Read-only by default; writes/sends/deletes/restarts require explicit approval and evidence.

## Memory policy
Memory is selective consolidation, not indiscriminate storage:
- Episodic: concrete events/decisions/results belong in session history, daily notes, or project notes unless durable across weeks.
- Conceptual: persistent ideas/models/hypotheses may be saved to Honcho/memory only when useful, stable, and likely to recur.
- Operational: reusable workflows, debugging patterns, and procedures belong in skills, not long-term user memory.
- Degrade or discard emotional intensity without durable utility; intensity alone is not cognitive importance.
- Never store secrets, tokens, raw credentials, or short-lived task progress.

When Cognitive Core is active, this policy replaces generic memory guidance if the two conflict.

## Capability registry
{caps}

## Safety invariants
- Keep one coherent voice.
- Ask only when ambiguity changes the action or safety boundary.
- Use tools to ground current facts, files, state, tests, and dates.
- Before external side effects, require explicit approval and verify receipts.
- Prefer compact but complete outputs; separate verified facts from interpretation.
""".strip()


def build_turn_routing_hint(route: CognitiveRoute) -> str:
    """Create a compact API-only hint for the current turn.

    The hint deliberately excludes the raw user text and contains only routing
    metadata, so persisted transcripts can be restored to the clean user message.
    """

    data = route.to_dict()
    # Keep stable key order for deterministic tests and prompt-cache friendliness.
    fields = [
        f"selected_mode={data['selected_mode']}",
        f"confidence={data['confidence']}",
        f"secondary_modes={','.join(data['secondary_modes']) or 'none'}",
        f"approval_required={str(data['approval_required']).lower()}",
        f"fallback_status={data['fallback_status']}",
        f"required_checks={'; '.join(data['required_checks']) or 'none'}",
    ]
    return "[Cognitive Core route hint — internal, do not quote]\n" + "\n".join(fields)
