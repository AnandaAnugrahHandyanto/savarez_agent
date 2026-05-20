"""Harness-agnostic core contracts for ContextOps/ESE.

These types are deliberately tiny and dependency-free. ContextOps/ESE is
cognitive-state middleware: Event -> Thread/Tension/EpistemicMode ->
StateDelta -> ContextPack. This skeleton only carries the *boundary* shapes
needed to build a safe context pack preview; it intentionally does not copy
the broader harness prototype logic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SCHEMA_VERSION = "contextops.contract.v0"
PolicyMode = Literal["read_only", "suggestion_only", "shadow", "disabled"]
SafetyDecisionStatus = Literal["allow_suggestion", "fail_closed", "blocked"]
FindingKind = Literal[
    "missing_origin_ack",
    "passive_delivery_mistaken_for_active_wake",
    "duplicate_remediation_loop",
]


def _schema_dict(obj: Any) -> dict[str, Any]:
    """Serialize a contract dataclass and assert its schema_version is present."""

    row = asdict(obj)
    if not isinstance(row.get("schema_version"), str) or not row["schema_version"]:
        raise ValueError("ContextOps contract DTO missing schema_version")
    return row


@dataclass(frozen=True)
class Observation:
    """One unit of harness-agnostic evidence fed to the preview builder.

    ``signal`` is the short cognitive label the *caller* already extracted
    (a stance, decision, or tension). ``raw_text`` is the full transcript
    fragment — it is kept only so the builder can size/scrub against it and
    is NEVER copied into a ContextPack. ``raw_id`` is opaque input; the
    builder replaces it with a derived safe ref.
    """

    raw_id: str
    signal: str
    raw_text: str = ""
    raw_refs: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _schema_dict(self)


@dataclass(frozen=True)
class ContextPack:
    """A compact restore/avoid contract — not a transcript or generic summary.

    Every string in ``restore``/``avoid``/``refs`` has passed the safety
    checks in :mod:`contextops_ese.preview`: no raw transcripts, no absolute
    paths, no raw ids.
    """

    id: str
    restore: tuple[str, ...]
    avoid: tuple[str, ...]
    refs: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _schema_dict(self)


@dataclass(frozen=True)
class PreviewConfig:
    """Behaviour flags for the preview builder.

    Defaults are fail-safe: the engine is disabled, runs preview-only, and
    never injects into a live prompt. A harness must opt in explicitly.
    """

    enabled: bool = False
    preview: bool = True
    inject: bool = False
    max_context_pack_chars: int = 4000
    include_raw_transcript: bool = False
    include_raw_ids: bool = False
    include_paths: bool = False

    avoid_signals: tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _schema_dict(self)


@dataclass(frozen=True)
class RuntimeEvent:
    """Read-only runtime event DTO for adapter-supplied observations.

    ``event_ref`` and ``evidence_refs`` are opaque refs only (``ref:<hex>``),
    never provider ids, message ids, task ids, file paths, or transcript text.
    ``source`` is a harness-agnostic label; adapters supply their own value.
    """

    event_ref: str
    event_type: str
    source: str = "unknown"
    policy_mode: PolicyMode = "read_only"
    evidence_refs: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _schema_dict(self)


@dataclass(frozen=True)
class MessageSummary:
    """Session/message summary DTO carrying labels and opaque refs only."""

    message_ref: str
    session_ref: str
    role: str = "unknown"
    summary: str = ""
    evidence_refs: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _schema_dict(self)


@dataclass(frozen=True)
class TaskHandoffAckObservation:
    """Read-only task/handoff/ack observation used by adapter detectors."""

    task_ref: str
    origin_ref: str | None = None
    return_to_ref: str | None = None
    delegated: bool = False
    completed: bool = False
    origin_ack_observed: bool = False
    delivery_mode: str = "unknown"
    trigger_agent: bool = False
    operator_expected_active_wake: bool = False
    remediation_group_ref: str | None = None
    pair_role: str = "unknown"
    evidence_refs: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _schema_dict(self)


@dataclass(frozen=True)
class SafetyDecision:
    """Fail-closed/suggestion-only policy decision for a report."""

    status: SafetyDecisionStatus = "allow_suggestion"
    policy_mode: PolicyMode = "suggestion_only"
    read_only: bool = True
    mutation_allowed: bool = False
    dispatch_allowed: bool = False
    reason: str = "suggestion-only report; operator owns action"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _schema_dict(self)


@dataclass(frozen=True)
class EvidenceBundle:
    """Opaque evidence references backing a finding."""

    evidence_refs: tuple[str, ...]
    summary: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _schema_dict(self)


@dataclass(frozen=True)
class Recommendation:
    """Operator-facing suggestion; never an automatic action."""

    routing_category: str
    suggested_operator_action: str
    policy_mode: PolicyMode = "suggestion_only"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _schema_dict(self)


@dataclass(frozen=True)
class Finding:
    """Suggestion-only finding with opaque evidence and a safety decision."""

    finding_ref: str
    kind: FindingKind
    title: str
    confidence: float
    evidence: EvidenceBundle
    recommendation: Recommendation
    safety_decision: SafetyDecision = field(default_factory=SafetyDecision)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        row = _schema_dict(self)
        row["evidence"] = self.evidence.to_dict()
        row["recommendation"] = self.recommendation.to_dict()
        row["safety_decision"] = self.safety_decision.to_dict()
        return row
