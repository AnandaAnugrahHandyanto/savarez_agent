"""Dialectical materialist belief structures for the Hermes memory system.

Extends the flat §-delimited memory entries with structured metadata stored
in a JSON sidecar file (MEMORY.meta.json / USER.meta.json). The entries
themselves remain §-delimited text for backward compatibility with the
frozen snapshot pattern and all existing tooling.

Design sources:
- Experience Engine: three-tier lifecycle, noise-aware scoring, probationary surfacing
- Merkraum: knowledge-type-specific decay, belief status state machine, contradiction edges
- MemEX: tri-score (authority/conviction/importance), provenance chains, cascade retraction
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MaturityLevel(IntEnum):
    """Knowledge maturity progression: INCIDENT -> PATTERN -> PRINCIPLE -> WISDOM."""
    INCIDENT = 0
    PATTERN = 1
    PRINCIPLE = 2
    WISDOM = 3


class BeliefStatus(Enum):
    """Lifecycle state machine for belief entries."""
    ACTIVE = "active"
    CONTRADICTED = "contradicted"
    SUPERSEDED = "superseded"
    DECAYED = "decayed"
    SYNTHESIZED = "synthesized"


class KnowledgeType(Enum):
    """Semantic category that governs decay rates. Orthogonal to MaturityLevel."""
    FACT = "fact"
    STATE = "state"
    RULE = "rule"
    BELIEF = "belief"
    MEMORY = "memory"


class SourceKind(Enum):
    """Provenance of a memory entry. Drives authority weighting."""
    USER_EXPLICIT = "user_explicit"
    OBSERVED = "observed"
    AGENT_INFERRED = "agent_inferred"
    USER_CORRECTION = "user_correction"
    BACKGROUND_REVIEW = "background_review"
    DERIVED = "derived"


class ContradictionMode(Enum):
    """How to handle contradictions at retrieval time."""
    SURFACE = "surface"
    FILTER = "filter"


# ---------------------------------------------------------------------------
# Core Data Structures
# ---------------------------------------------------------------------------

@dataclass
class EntryMeta:
    """Structured metadata for a single memory entry.

    Stored alongside the entry text in MEMORY.meta.json / USER.meta.json.
    Keyed by entry_id (uuid4). The entry text itself remains in the
    §-delimited file for backward compatibility.
    """

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    maturity: MaturityLevel = MaturityLevel.INCIDENT
    knowledge_type: KnowledgeType = KnowledgeType.BELIEF
    source_kind: SourceKind = SourceKind.USER_EXPLICIT
    status: BeliefStatus = BeliefStatus.ACTIVE

    authority: float = 0.7
    conviction: float = 0.7
    importance: float = 0.7
    confidence: float = 0.7

    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_validated_at: float = field(default_factory=time.time)

    hit_count: int = 0
    surface_count: int = 0
    ignore_count: int = 0
    observed_behavior_count: int = 0

    contradiction_ids: List[str] = field(default_factory=list)
    contradiction_count: int = 0
    synthesis_id: Optional[str] = None

    parent_ids: List[str] = field(default_factory=list)
    child_ids: List[str] = field(default_factory=list)

    superseded_by: Optional[str] = None

    original_text: Optional[str] = None
    principle_text: Optional[str] = None

    scope: Dict[str, str] = field(
        default_factory=lambda: {"lang": "all", "framework": "any", "project": "any"}
    )

    noise_context: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict. Enums become their string values."""
        return {
            "entry_id": self.entry_id,
            "maturity": self.maturity.value,
            "knowledge_type": self.knowledge_type.value,
            "source_kind": self.source_kind.value,
            "status": self.status.value,
            "authority": self.authority,
            "conviction": self.conviction,
            "importance": self.importance,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_validated_at": self.last_validated_at,
            "hit_count": self.hit_count,
            "surface_count": self.surface_count,
            "ignore_count": self.ignore_count,
            "observed_behavior_count": self.observed_behavior_count,
            "contradiction_ids": list(self.contradiction_ids),
            "contradiction_count": self.contradiction_count,
            "synthesis_id": self.synthesis_id,
            "parent_ids": list(self.parent_ids),
            "child_ids": list(self.child_ids),
            "superseded_by": self.superseded_by,
            "original_text": self.original_text,
            "principle_text": self.principle_text,
            "scope": dict(self.scope),
            "noise_context": [dict(nc) for nc in self.noise_context],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EntryMeta":
        """Deserialize from dict. Handles missing fields for forward compat."""
        def _get(key: str, default=None):
            return d[key] if key in d else default

        meta = cls()
        meta.entry_id = _get("entry_id", meta.entry_id)
        meta.maturity = MaturityLevel(_get("maturity", meta.maturity.value))
        meta.knowledge_type = KnowledgeType(_get("knowledge_type", meta.knowledge_type.value))
        meta.source_kind = SourceKind(_get("source_kind", meta.source_kind.value))
        meta.status = BeliefStatus(_get("status", meta.status.value))

        meta.authority = float(_get("authority", meta.authority))
        meta.conviction = float(_get("conviction", meta.conviction))
        meta.importance = float(_get("importance", meta.importance))
        meta.confidence = float(_get("confidence", meta.confidence))

        meta.created_at = float(_get("created_at", meta.created_at))
        meta.updated_at = float(_get("updated_at", meta.updated_at))
        meta.last_validated_at = float(_get("last_validated_at", meta.last_validated_at))

        meta.hit_count = int(_get("hit_count", meta.hit_count))
        meta.surface_count = int(_get("surface_count", meta.surface_count))
        meta.ignore_count = int(_get("ignore_count", meta.ignore_count))
        meta.observed_behavior_count = int(_get("observed_behavior_count", meta.observed_behavior_count))

        meta.contradiction_ids = list(_get("contradiction_ids", []))
        meta.contradiction_count = int(_get("contradiction_count", 0))
        meta.synthesis_id = _get("synthesis_id", None)

        meta.parent_ids = list(_get("parent_ids", []))
        meta.child_ids = list(_get("child_ids", []))
        meta.superseded_by = _get("superseded_by", None)

        meta.original_text = _get("original_text", None)
        meta.principle_text = _get("principle_text", None)

        meta.scope = dict(_get("scope", {"lang": "all", "framework": "any", "project": "any"}))
        meta.noise_context = [dict(nc) for nc in _get("noise_context", [])]

        return meta


@dataclass
class ContradictionEdge:
    """A contradiction relationship between two entries. First-class object."""

    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_id: str = ""
    to_id: str = ""
    reason: str = ""
    confidence: float = 0.8
    author: str = "agent"
    created_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolution_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id, "from_id": self.from_id, "to_id": self.to_id,
            "reason": self.reason, "confidence": self.confidence, "author": self.author,
            "created_at": self.created_at, "resolved": self.resolved,
            "resolution_id": self.resolution_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ContradictionEdge":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class MetaStore:
    """The JSON sidecar file structure for one memory target."""

    version: int = 1
    entries: Dict[str, EntryMeta] = field(default_factory=dict)
    contradictions: List[ContradictionEdge] = field(default_factory=list)
    text_to_id: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "contradictions": [c.to_dict() for c in self.contradictions],
            "text_to_id": self.text_to_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MetaStore":
        entries = {k: EntryMeta.from_dict(v) for k, v in d.get("entries", {}).items()}
        contradictions = [ContradictionEdge.from_dict(c) for c in d.get("contradictions", [])]
        return cls(
            version=d.get("version", 1), entries=entries,
            contradictions=contradictions, text_to_id=d.get("text_to_id", {}),
        )


# ---------------------------------------------------------------------------
# Configuration Constants
# ---------------------------------------------------------------------------

DECAY_CONFIG: Dict[KnowledgeType, Dict[str, Any]] = {
    KnowledgeType.FACT:   {"rate_per_day": None,   "floor": 0.5},
    KnowledgeType.STATE:  {"rate_per_day": 0.02,   "floor": 0.1},
    KnowledgeType.RULE:   {"rate_per_day": 0.002,  "floor": 0.3},
    KnowledgeType.BELIEF: {"rate_per_day": 0.005,  "floor": 0.1},
    KnowledgeType.MEMORY: {"rate_per_day": 0.001,  "floor": 0.2},
}

MATURITY_CONFIDENCE_FLOOR: Dict[MaturityLevel, float] = {
    MaturityLevel.INCIDENT: 0.3,
    MaturityLevel.PATTERN: 0.4,
    MaturityLevel.PRINCIPLE: 0.5,
    MaturityLevel.WISDOM: 0.7,
}

SOURCE_AUTHORITY_DEFAULT: Dict[SourceKind, float] = {
    SourceKind.USER_EXPLICIT: 0.9,
    SourceKind.OBSERVED: 0.95,
    SourceKind.USER_CORRECTION: 0.95,
    SourceKind.AGENT_INFERRED: 0.5,
    SourceKind.BACKGROUND_REVIEW: 0.6,
    SourceKind.DERIVED: 0.4,
}

PROMOTION_THRESHOLDS = {
    MaturityLevel.INCIDENT: {"min_hit_count": 2, "min_age_days": 3, "min_confidence": 0.5},
    MaturityLevel.PATTERN:  {"min_hit_count": 5, "min_age_days": 7, "min_confidence": 0.6},
    MaturityLevel.PRINCIPLE: {"min_hit_count": 10, "min_age_days": 14, "min_confidence": 0.7},
}

DEMOTION_THRESHOLDS = {
    "ignore_ratio_for_supersede": 0.5,
    "min_surfaces_for_supersede": 5,
    "contradiction_count_for_demote": 2,
    "confidence_for_decay_demote": 0.2,
}


# ---------------------------------------------------------------------------
# Pure Functions
# ---------------------------------------------------------------------------

def text_hash(text: str) -> str:
    """Stable hash for entry text matching. Uses sha256 for collision resistance."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def compute_decayed_confidence(meta: EntryMeta, now: float = None) -> float:
    """Compute effective confidence after time-based decay.

    Facts never decay. Recently validated (< 1 day) skip decay.
    Observed behavior decays at half speed. Maturity provides a floor.
    """
    if now is None:
        now = time.time()

    config = DECAY_CONFIG.get(meta.knowledge_type, DECAY_CONFIG[KnowledgeType.BELIEF])
    rate = config["rate_per_day"]
    type_floor = config["floor"]

    if rate is None:
        return meta.confidence

    days_since_validation = (now - meta.last_validated_at) / 86400
    if days_since_validation < 1.0:
        return meta.confidence

    days_since_update = (now - meta.updated_at) / 86400
    if days_since_update < 1.0:
        return meta.confidence

    decay_multiplier = (1 - rate) ** days_since_update

    if meta.observed_behavior_count > 0 and meta.source_kind == SourceKind.OBSERVED:
        decay_multiplier = decay_multiplier ** 0.5

    decayed = meta.confidence * decay_multiplier

    maturity_floor = MATURITY_CONFIDENCE_FLOOR.get(meta.maturity, 0.3)
    effective_floor = max(type_floor, maturity_floor)

    return max(effective_floor, decayed)


def compute_effective_score(meta: EntryMeta, cosine_similarity: float, now: float = None) -> float:
    """Compute final ranking score for retrieval."""
    if now is None:
        now = time.time()

    confidence = compute_decayed_confidence(meta, now)

    is_seed = meta.source_kind in (SourceKind.BACKGROUND_REVIEW, SourceKind.DERIVED)
    hit_boost = 0.0 if is_seed else min(0.12, (meta.hit_count ** 0.5) * 0.03)

    days_since_hit = (now - meta.last_validated_at) / 86400 if meta.last_validated_at else 999
    recency_penalty = min(0.15, max(0, (days_since_hit - 30) / 335 * 0.15))

    ignore_penalty = min(0.30, meta.ignore_count * 0.05)

    noise_penalty = 0.0
    for nc in meta.noise_context:
        if nc.get("reason") == "stale_rule":
            noise_penalty += 0.06
        elif nc.get("reason") == "wrong_context":
            noise_penalty += 0.04
    noise_penalty = min(0.18, noise_penalty)

    superseded_penalty = 0.5 if meta.status == BeliefStatus.SUPERSEDED else 0.0

    raw = (cosine_similarity + hit_boost - recency_penalty
           - ignore_penalty - noise_penalty - superseded_penalty)

    return raw * (0.6 + 0.4 * confidence)


def evaluate_promotion(meta: EntryMeta, now: float = None) -> Optional[MaturityLevel]:
    """Check if entry qualifies for maturity promotion. Returns target level or None."""
    if now is None:
        now = time.time()

    if meta.maturity == MaturityLevel.WISDOM:
        return None

    current = meta.maturity
    target = MaturityLevel(current + 1)
    thresholds = PROMOTION_THRESHOLDS.get(current)
    if not thresholds:
        return None

    age_days = (now - meta.created_at) / 86400
    effective_hits = meta.hit_count + meta.observed_behavior_count

    if effective_hits < thresholds["min_hit_count"]:
        return None
    if age_days < thresholds["min_age_days"]:
        return None
    if compute_decayed_confidence(meta, now) < thresholds["min_confidence"]:
        return None

    return target


def promote_entry(meta: EntryMeta, target: MaturityLevel,
                  entry_text: str = "", llm_call: Callable = None) -> EntryMeta:
    """Promote entry to higher maturity level."""
    meta.maturity = target
    meta.updated_at = time.time()

    if target == MaturityLevel.PATTERN:
        meta.authority = max(meta.authority, 0.7)
    elif target == MaturityLevel.PRINCIPLE:
        meta.authority = max(meta.authority, 0.8)
        meta.conviction = max(meta.conviction, 0.7)
    elif target == MaturityLevel.WISDOM:
        meta.authority = max(meta.authority, 0.9)
        meta.confidence = max(meta.confidence, 0.8)

    return meta


def resolve_contradiction(entry_a: EntryMeta, entry_b: EntryMeta,
                          text_a: str, text_b: str, resolution_text: str,
                          llm_call: Callable = None) -> Tuple[EntryMeta, str]:
    """Resolve contradiction by creating a synthesis entry."""
    synthesis = EntryMeta(
        maturity=max(entry_a.maturity, entry_b.maturity),
        knowledge_type=entry_a.knowledge_type,
        source_kind=SourceKind.DERIVED,
        status=BeliefStatus.ACTIVE,
        authority=max(entry_a.authority, entry_b.authority),
        conviction=0.8,
        importance=max(entry_a.importance, entry_b.importance),
        confidence=0.8,
        parent_ids=[entry_a.entry_id, entry_b.entry_id],
        scope=_merge_scopes(entry_a.scope, entry_b.scope),
    )

    entry_a.status = BeliefStatus.SYNTHESIZED
    entry_a.synthesis_id = synthesis.entry_id
    entry_b.status = BeliefStatus.SYNTHESIZED
    entry_b.synthesis_id = synthesis.entry_id

    return synthesis, resolution_text


def _merge_scopes(scope_a: Dict[str, str], scope_b: Dict[str, str]) -> Dict[str, str]:
    """Merge scopes via majority vote. Disagree -> wildcard."""
    merged = {}
    for key in set(scope_a) | set(scope_b):
        val_a = scope_a.get(key, "any")
        val_b = scope_b.get(key, "any")
        merged[key] = val_a if val_a == val_b else "any"
    return merged


def record_hit(meta: EntryMeta, context: Dict[str, str] = None) -> EntryMeta:
    """Record successful use. Revalidates the entry."""
    meta.hit_count += 1
    meta.last_validated_at = time.time()
    meta.updated_at = time.time()
    boost = min(meta.hit_count * 0.01, 0.15)
    meta.confidence = min(1.0, meta.confidence + boost)
    return meta


def record_surface(meta: EntryMeta, context: Dict[str, str] = None) -> EntryMeta:
    """Record that entry was surfaced in context."""
    meta.surface_count += 1
    return meta


def record_ignore(meta: EntryMeta, context: Dict[str, str] = None,
                  reason: str = "agent_skipped") -> EntryMeta:
    """Record that agent saw entry but didn't use it."""
    meta.ignore_count += 1
    ctx = dict(context) if context is not None else {}
    ctx["reason"] = reason
    meta.noise_context.append(ctx)
    if len(meta.noise_context) > 50:
        meta.noise_context = meta.noise_context[-50:]
    return meta


def record_observed_behavior(meta: EntryMeta) -> EntryMeta:
    """Record that user's behavior confirmed this entry."""
    meta.observed_behavior_count += 1
    meta.last_validated_at = time.time()
    meta.authority = min(1.0, meta.authority + 0.02)
    return meta


def check_validation_decay(meta: EntryMeta, now: float = None) -> Optional[BeliefStatus]:
    """Check if entry should transition to DECAYED status.

    Uses raw confidence (before maturity floor) because the floor is for
    retrieval ranking, not for decay decisions.
    """
    if now is None:
        now = time.time()

    if meta.status != BeliefStatus.ACTIVE:
        return None

    config = DECAY_CONFIG.get(meta.knowledge_type, DECAY_CONFIG[KnowledgeType.BELIEF])
    rate = config["rate_per_day"]
    if rate is None:
        return None

    days_since_update = (now - meta.updated_at) / 86400
    raw_decayed = meta.confidence * ((1 - rate) ** days_since_update)

    if raw_decayed < DEMOTION_THRESHOLDS["confidence_for_decay_demote"]:
        return BeliefStatus.DECAYED

    return None
