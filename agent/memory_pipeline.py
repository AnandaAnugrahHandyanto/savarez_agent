"""MemoryPipeline -- organic memory infrastructure inside MemoryManager.

NOT a MemoryProvider.  No name, no tools, no system_prompt_block.
Pure interceptor: executes organic logic before/after MemoryManager lifecycle methods.

All methods are best-effort: exceptions are caught and logged at debug level,
never blocking upstream providers.

Design philosophy (浑然一体):
    Memory's organic properties (salience gating, silent engrams, consolidation,
    reconsolidation, predictive feedback, spreading activation) are infrastructure
    of the entire cognitive system -- not features of a specific storage backend.
    Just as synaptic plasticity is a universal property of neural circuits, not
    a "plugin" for the hippocampus, the MemoryPipeline lives inside MemoryManager
    and operates on ALL memory pathways regardless of which provider is active.

Architecture:
    MemoryManager
        └── MemoryPipeline (interceptor layer, NOT a provider)
            ├── SalienceScorer      (Layer 1: sensory gate)
            ├── SilentEngramEngine  (Layer 2: availability continuum)
            ├── ConsolidationEngine (Layer 3: sleep-like consolidation)
            ├── ReconsolidationEngine (Layer 4: prediction-error updates)
            ├── FeedbackCoordinator (Layer 5: predictive processing + learning)
            └── ActivationGraph     (Layer 6: spreading activation)
        └── providers[] (builtin + one external)

5 Architectural Invariants Preserved:
    1. MemoryProvider ABC contract unchanged
    2. Single external provider limit unchanged
    3. Tool registry unchanged (pipeline exposes no tools)
    4. ContextEngine orthogonality preserved
    5. run_agent.py integration points unchanged
"""

from __future__ import annotations

import logging
import math
import re
import sqlite3
import threading
from collections import deque
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layer 1: SalienceScorer (embedded — no external dependencies)
# ---------------------------------------------------------------------------

_EMOTION_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"[!！]{2,}"), 0.6),
    (re.compile(r"\b(urgent|critical|emergency|broken|crash|bug|fail)\b", re.I), 0.5),
    (re.compile(r"\b(down|outage|corrupt|overload|timeout|deadlock)\b", re.I), 0.45),
    (re.compile(r"\b(love|hate|amazing|terrible|awesome|awful)\b", re.I), 0.3),
    (re.compile(r"\b(worried|excited|frustrated|angry|happy|sad)\b", re.I), 0.35),
    (re.compile(r"\b(important|crucial|vital|essential|key)\b", re.I), 0.4),
]

_IMPORTANCE_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\b(decided|decision|agreed|confirmed|final)\b", re.I), 0.7),
    (re.compile(r"\b(requirement|spec|specification|constraint)\b", re.I), 0.6),
    (re.compile(r"\b(deploy|release|production|launch)\b", re.I), 0.6),
    (re.compile(r"\b(architecture|design|refactor|migrat)\b", re.I), 0.5),
    (re.compile(r"\b(remember|note|important|don't forget)\b", re.I), 0.8),
    (re.compile(r"\b(prefer|always|never|usually)\b", re.I), 0.5),
    (re.compile(r"\b(bug|issue|error|problem)\b", re.I), 0.4),
]

_TRIVIAL_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"^(hi|hello|hey|thanks|ok|yes|no|sure)\s*[.!?]?\s*$", re.I), 0.9),
    (re.compile(r"^(good morning|good night|bye|see you)", re.I), 0.8),
    (re.compile(r"^(what time|what date|weather)", re.I), 0.5),
]


@dataclass
class SalienceResult:
    """Multi-dimensional salience score for a message."""
    overall: float = 0.0
    emotion: float = 0.0
    novelty: float = 0.5
    importance: float = 0.0
    repetition_penalty: float = 1.0
    is_trivial: bool = False


@dataclass
class _RepetitionDetector:
    """Detects topic repetition using content hashing (F3 power-law penalty)."""
    window_size: int = 50
    _recent: deque = field(default_factory=lambda: deque(maxlen=50))
    _topic_counts: dict[str, int] = field(default_factory=dict)

    def _fuzzy_bucket(self, text: str) -> str:
        words = [w for w in re.sub(r"[^\w\s]", "", text.lower()).split() if len(w) > 2]
        return " ".join(words[:5])

    def observe(self, text: str) -> float:
        bucket = self._fuzzy_bucket(text)
        if not bucket:
            return 1.0
        self._topic_counts[bucket] = self._topic_counts.get(bucket, 0) + 1
        self._recent.append(bucket)
        if len(self._recent) == self._recent.maxlen or len(self._topic_counts) > self._recent.maxlen * 2:
            window_counts: dict[str, int] = {}
            for b in self._recent:
                window_counts[b] = window_counts.get(b, 0) + 1
            for topic in list(self._topic_counts):
                if topic not in window_counts:
                    del self._topic_counts[topic]
                else:
                    self._topic_counts[topic] = window_counts[topic]
        n = self._topic_counts.get(bucket, 1)
        return max(0.1, 1.0 / math.sqrt(n))

    def reset(self) -> None:
        self._recent.clear()
        self._topic_counts.clear()


class SalienceScorer:
    """Multi-dimensional salience scorer — the sensory gate.

    Pure rule-based — no LLM calls, O(message_length) time.
    Scores: emotion, novelty, importance, repetition penalty.
    """

    def __init__(self, novelty_window: int = 50) -> None:
        self._rep = _RepetitionDetector(window_size=novelty_window)

    def score(self, message: str) -> SalienceResult:
        if not message or not message.strip():
            return SalienceResult(overall=0.0, is_trivial=True)
        text = message.strip()

        # Trivial detection
        trivial_penalty = 1.0
        for pattern, weight in _TRIVIAL_PATTERNS:
            if pattern.search(text):
                trivial_penalty = min(trivial_penalty, 1.0 - weight)
        is_trivial = trivial_penalty < 0.3

        # Emotion signal
        emotion = 0.0
        for pattern, weight in _EMOTION_PATTERNS:
            if pattern.search(text):
                emotion = max(emotion, weight)
        if len(text) < 20:
            emotion *= 0.5

        # Importance signal
        importance = 0.0
        for pattern, weight in _IMPORTANCE_PATTERNS:
            if pattern.search(text):
                importance = max(importance, weight)
        if len(text) > 200:
            importance = min(1.0, importance + 0.1)

        # Novelty + repetition penalty
        freshness = self._rep.observe(text)
        novelty = freshness
        rep_factor = freshness

        # Combine
        raw = (0.25 * emotion + 0.30 * novelty + 0.30 * importance
               + 0.15 * min(1.0, len(text) / 200))
        adjusted = raw * rep_factor * (1.0 - (1.0 - trivial_penalty) * 0.8)
        overall = max(0.0, min(1.0, adjusted))

        return SalienceResult(
            overall=overall, emotion=emotion, novelty=novelty,
            importance=importance, repetition_penalty=rep_factor,
            is_trivial=is_trivial,
        )

    def reset(self) -> None:
        self._rep = _RepetitionDetector(window_size=self._rep.window_size)


# ---------------------------------------------------------------------------
# Pipeline Schema (full database provisioning)
# ---------------------------------------------------------------------------

_PIPELINE_SCHEMA = """\
-- Layer 1: Salience learning state
CREATE TABLE IF NOT EXISTS salience_weights (
    signal_type     TEXT PRIMARY KEY,
    weight          REAL NOT NULL,
    sample_count    INTEGER DEFAULT 0,
    success_count   INTEGER DEFAULT 0,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS salience_encoding_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    fact_ref        TEXT,
    emotion_score   REAL,
    novelty_score   REAL,
    importance_score REAL,
    overall_score   REAL,
    was_helpful     INTEGER DEFAULT -1,
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Layer 2: Silent Engram state (cross-provider strength tracking)
CREATE TABLE IF NOT EXISTS engram_strengths (
    memory_ref      TEXT PRIMARY KEY,
    provider        TEXT NOT NULL,
    strength        REAL DEFAULT 1.0,
    last_accessed   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decay_half_life_hours REAL DEFAULT 720.0,
    access_count    INTEGER DEFAULT 0
);

-- Layer 3: Schema Store (neocortical semantic knowledge)
CREATE TABLE IF NOT EXISTS schemas (
    schema_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    content         TEXT NOT NULL,
    domain          TEXT DEFAULT 'general',
    confidence      REAL DEFAULT 0.5,
    source_count    INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hrr_vector      BLOB
);

CREATE TABLE IF NOT EXISTS schema_sources (
    schema_id       INTEGER REFERENCES schemas(schema_id),
    memory_ref      TEXT NOT NULL,
    provider        TEXT NOT NULL,
    contribution    REAL DEFAULT 1.0,
    PRIMARY KEY (schema_id, memory_ref)
);

CREATE TABLE IF NOT EXISTS reconsolidation_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_ref      TEXT,
    old_content     TEXT,
    new_content     TEXT,
    prediction_error REAL,
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS consolidation_runs (
    run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT,
    memories_processed INTEGER DEFAULT 0,
    schemas_created INTEGER DEFAULT 0,
    schemas_updated INTEGER DEFAULT 0,
    conflicts_found INTEGER DEFAULT 0,
    duration_ms     INTEGER DEFAULT 0,
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Layer 4: Prediction state
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_id       INTEGER,
    prediction      TEXT NOT NULL,
    context         TEXT DEFAULT '',
    outcome         TEXT DEFAULT '',
    error_score     REAL DEFAULT 0.0,
    resolved        INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at     TIMESTAMP
);

-- Layer 5: Salience Feedback
CREATE TABLE IF NOT EXISTS salience_feedback (
    feedback_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_ref      TEXT,
    signal_type     TEXT,
    signal_value    REAL,
    was_helpful     INTEGER DEFAULT 0,
    was_retrieved   INTEGER DEFAULT 0,
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Layer 6: Co-Activation Graph (spreading activation)
CREATE TABLE IF NOT EXISTS activation_edges (
    source_entity   TEXT NOT NULL,
    target_entity   TEXT NOT NULL,
    strength        REAL DEFAULT 0.1,
    co_activation_count INTEGER DEFAULT 1,
    last_activated  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_entity, target_entity)
);

CREATE TABLE IF NOT EXISTS cross_domain_links (
    link_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    entity          TEXT NOT NULL,
    domain_a        TEXT NOT NULL,
    domain_b        TEXT NOT NULL,
    fact_refs_a     TEXT DEFAULT '',
    fact_refs_b     TEXT DEFAULT '',
    strength        REAL DEFAULT 0.5,
    discovered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_engram_strength ON engram_strengths(strength DESC);
CREATE INDEX IF NOT EXISTS idx_engram_provider ON engram_strengths(provider);
CREATE INDEX IF NOT EXISTS idx_schemas_domain ON schemas(domain);
CREATE INDEX IF NOT EXISTS idx_schemas_confidence ON schemas(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_activation_source ON activation_edges(source_entity);
CREATE INDEX IF NOT EXISTS idx_activation_target ON activation_edges(target_entity);
CREATE INDEX IF NOT EXISTS idx_cross_links_entity ON cross_domain_links(entity);
CREATE INDEX IF NOT EXISTS idx_salience_feedback_ref ON salience_feedback(memory_ref, was_retrieved);
"""


# ---------------------------------------------------------------------------
# PipelineState -- persistent storage for organic memory modules
# ---------------------------------------------------------------------------

class PipelineState:
    """Persistent state for the memory pipeline (pipeline_state.db).

    Design constraints:
    - Single connection + threading.RLock (same pattern as MemoryStore in store.py)
    - WAL mode (same as store.py via apply_wal_with_fallback)
    - Independent from any provider's database connection

    References to provider memories use ``memory_ref`` (format:
    ``{provider_name}:{native_id}`` or content hash), NOT foreign keys.
    This ensures cross-provider decoupling.
    """

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            from hermes_constants import get_hermes_home
            db_path = str(get_hermes_home() / "pipeline_state.db")
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=10.0,
        )
        self._lock = threading.RLock()
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        """Create all pipeline tables if they do not exist. Enable WAL mode."""
        from hermes_state import apply_wal_with_fallback
        apply_wal_with_fallback(self._conn, db_label="pipeline_state.db")
        with self._lock:
            self._conn.executescript(_PIPELINE_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        """Close the database connection. Idempotent."""
        try:
            self._conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# MemoryPipeline -- the interceptor layer
# ---------------------------------------------------------------------------

class MemoryPipeline:
    """Organic memory pipeline -- internal infrastructure of MemoryManager.

    NOT a MemoryProvider.  Has no name, does not expose tools, does not
    produce system_prompt_block.  Pure interceptor: wraps MemoryManager
    lifecycle methods to execute organic logic before/after providers.

    All methods are best-effort: exceptions are caught and logged at
    debug level, never blocking upstream providers.

    Phase 1: All methods are no-op stubs.  The pipeline skeleton establishes
    the plumbing so that Phase 2 (extracting modules from Holographic) can
    proceed without ever touching MemoryManager again.
    """

    def __init__(self, config: dict | None = None) -> None:
        self._config: dict = config or {}
        self._state: PipelineState | None = None
        self._enabled: bool = self._config.get("enabled", True)
        # Layer references -- populated as phases are implemented
        self._salience = None          # Phase 2: SalienceScorer
        self._silent_engram = None     # Phase 3: SilentEngramEngine
        self._consolidation = None     # Phase 4: ConsolidationEngine
        self._reconsolidation = None   # Phase 4: ReconsolidationEngine
        self._feedback = None          # Phase 5: FeedbackCoordinator
        self._activation = None        # Phase 6: ActivationGraph

    def initialize(self, session_id: str, **kwargs) -> None:
        """Initialize pipeline state database and organic modules.

        Called from MemoryManager.initialize_all() BEFORE providers init.
        """
        if not self._enabled:
            return
        db_path = self._config.get("db_path") or None
        self._state = PipelineState(db_path=db_path)

        # Phase 2: Initialize SalienceScorer
        salience_cfg = self._config.get("salience", {})
        if salience_cfg.get("enabled", True):
            try:
                window = salience_cfg.get("novelty_window", 50)
                self._salience = SalienceScorer(novelty_window=window)
                logger.debug("SalienceScorer initialized (window=%d)", window)
            except Exception as e:
                logger.debug("SalienceScorer init failed: %s", e)

        logger.debug("MemoryPipeline initialized (session=%s)", session_id)

    def shutdown(self) -> None:
        """Flush and close pipeline state.

        Called from MemoryManager.shutdown_all() BEFORE providers shutdown.
        """
        if self._state is not None:
            self._state.close()
            self._state = None
        logger.debug("MemoryPipeline shut down")

    # -- Pre-interceptors (called BEFORE provider operations) --

    def pre_turn_start(self, turn: int, message: str) -> None:
        """Called before providers' on_turn_start.

        Phase 2: reset salience novelty window every 100 turns to prevent
        stale topic counts from dominating.
        """
        if self._salience and turn > 0 and turn % 100 == 0:
            try:
                self._salience.reset()
                logger.debug("SalienceScorer reset at turn %d", turn)
            except Exception as e:
                logger.debug("SalienceScorer reset failed: %s", e)

    def pre_sync(self, user: str, asst: str) -> dict | None:
        """Called before providers' sync_turn.

        Returns salience metadata for providers that support it.
        Phase 2: score user content for salience, return signals.
        """
        if not self._salience:
            return None
        try:
            result = self._salience.score(user)
            # Log encoding for learning
            if self._state:
                with self._state._lock:
                    self._state._conn.execute(
                        "INSERT INTO salience_encoding_log "
                        "(source, emotion_score, novelty_score, importance_score, overall_score) "
                        "VALUES (?, ?, ?, ?, ?)",
                        ("builtin", result.emotion, result.novelty,
                         result.importance, result.overall),
                    )
                    self._state._conn.commit()
            return {
                "salience_overall": result.overall,
                "salience_emotion": result.emotion,
                "salience_novelty": result.novelty,
                "salience_importance": result.importance,
                "salience_is_trivial": result.is_trivial,
            }
        except Exception as e:
            logger.debug("SalienceScorer.score failed: %s", e)
            return None

    def pre_memory_write(
        self, action: str, target: str, content: str, metadata: dict
    ) -> dict | None:
        """Called before providers' on_memory_write.

        Phase 2: salience gate -- score content and attach salience metadata.
        Does NOT block writes (that would require changing MemoryManager's
        return type). Instead, enriches metadata so providers can decide.
        """
        if not self._salience or action not in ("add", "replace"):
            return None
        try:
            result = self._salience.score(content)
            # Persist salience signal for learning
            if self._state:
                with self._state._lock:
                    self._state._conn.execute(
                        "INSERT INTO salience_encoding_log "
                        "(source, fact_ref, emotion_score, novelty_score, "
                        "importance_score, overall_score) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (target, content[:100], result.emotion, result.novelty,
                         result.importance, result.overall),
                    )
                    self._state._conn.commit()
            # Return enriched metadata for providers
            return {
                **metadata,
                "pipeline_salience": result.overall,
                "pipeline_emotion": result.emotion,
                "pipeline_novelty": result.novelty,
                "pipeline_importance": result.importance,
            }
        except Exception as e:
            logger.debug("SalienceScorer pre_memory_write failed: %s", e)
            return None

    def pre_compress(self, messages: list) -> str:
        """Called before providers' on_pre_compress.

        Returns insights text to include in compression summary.
        Phase 1: returns empty string.
        Phase 2: extract key facts from messages about to be discarded.
        """
        return ""

    # -- Post-interceptors (called AFTER provider operations) --

    def post_prefetch(self, query: str, provider_results: list[str]) -> str:
        """Called after providers' prefetch.

        Returns augmented context to append to prefetch results.
        Phase 1: returns empty string (no augmentation).
        Phase 2: spontaneous recovery, predictions, spreading activation.
        """
        return ""

    def post_tool_call(self, name: str, args: dict, result: str) -> None:
        """Called after provider's handle_tool_call.

        Phase 1: no-op.
        Phase 2: record retrieval for reconsolidation, feedback learning,
        co-activation recording.
        """
        pass

    def post_session_end(self, messages: list) -> None:
        """Called BEFORE providers' on_session_end.

        Phase 1: no-op.
        Phase 2: apply engram decay, run consolidation, discover bridges.
        """
        pass

    def post_session_switch(self, new_id: str, **kwargs) -> None:
        """Called after providers' on_session_switch.

        Phase 1: no-op.
        Phase 2: update per-session consolidation state.
        """
        pass

    def post_delegation(self, task: str, result: str, **kwargs) -> None:
        """Called after providers' on_delegation.

        Phase 1: no-op.
        Phase 2: score subagent result, extract high-salience facts.
        """
        pass

    def augment_system_prompt(self) -> str:
        """Called after providers' system_prompt_block.

        Returns text to append to the system prompt.
        Phase 1: returns empty string.
        Phase 2: inject organic memory status (silent count, schema count).
        """
        return ""


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_pipeline_config() -> dict:
    """Load memory.pipeline config from $HERMES_HOME/config.yaml.

    Returns an empty dict if the section is missing or config is unreadable.
    Uses lazy imports to avoid circular dependency with hermes_cli.config.
    """
    try:
        from hermes_cli.config import cfg_get, load_config
        config = load_config()
        return cfg_get(config, "memory", "pipeline", default={}) or {}
    except Exception as e:
        logger.debug("Failed to load pipeline config: %s", e)
        return {}
