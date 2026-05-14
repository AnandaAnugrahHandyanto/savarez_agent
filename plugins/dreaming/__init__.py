"""
Dreaming plugin — automatic background memory consolidation for Hermes Agent.

Inspired by biological sleep cycles and OpenClaw's Dreaming system, this plugin
runs during configured quiet hours to:

1. **Light Sleep** — Scan recent session transcripts, deduplicate, and stage
   candidate memories (short-term → staging area).
2. **REM Sleep** — Reflect on patterns, themes, and recurring ideas across
   conversations. Produces a human-readable Dream Diary entry.
3. **Deep Sleep** — Score candidates using weighted signals (relevance,
   frequency, recency, conceptual richness) and promote the highest-scoring
   entries into MEMORY.md.

The dreaming cycle is managed as a cron job that auto-registers on gateway
start. It respects user activity — if the user was recently active, the cycle
skips to avoid interrupting conversations.

Config (in config.yaml under ``plugins.entries.dreaming.config``):

    dreaming:
      enabled: true
      frequency: "0 3 * * *"        # cron expression (default: 3 AM daily)
      quiet_minutes: 60              # skip if user active within N minutes
      model: null                    # null = use default model
      max_candidates: 50             # max candidates to stage per cycle
      promotion_threshold: 0.6       # min score to promote (0-1)
      min_recall_count: 2            # min times a topic must appear
      dream_diary_path: null         # null = MEMORY_DIR/DREAMS.md
      memory_file_glob: "*.md"       # glob for memory files to scan
      lookback_days: 7               # how many days of sessions to review
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLUGIN_NAME = "dreaming"
DEFAULT_FREQUENCY = "0 3 * * *"
DEFAULT_QUIET_MINUTES = 60
DEFAULT_MAX_CANDIDATES = 50
DEFAULT_PROMOTION_THRESHOLD = 0.6
DEFAULT_MIN_RECALL_COUNT = 2
DEFAULT_LOOKBACK_DAYS = 7

# Scoring weights (must sum to ~1.0)
WEIGHT_RELEVANCE = 0.30
WEIGHT_FREQUENCY = 0.24
WEIGHT_QUERY_DIVERSITY = 0.15
WEIGHT_RECENCY = 0.15
WEIGHT_CONSOLIDATION = 0.10
WEIGHT_CONCEPTUAL_RICHNESS = 0.06

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Candidate:
    """A staged memory candidate produced by the Light phase."""

    def __init__(self, text: str, source: str = "", timestamp: Optional[datetime] = None):
        self.text = text.strip()
        self.source = source  # e.g. session ID or file path
        self.timestamp = timestamp or datetime.now(tz=timezone.utc)
        self.frequency: int = 1  # how many times this topic appeared
        self.score: float = 0.0
        self.score_breakdown: Dict[str, float] = {}

    def __repr__(self):
        return f"Candidate({self.text[:60]!r}, score={self.score:.2f}, freq={self.frequency})"


class DreamDiaryEntry:
    """A single dreaming cycle's output."""

    def __init__(self):
        self.timestamp: datetime = datetime.now(tz=timezone.utc)
        self.light_count: int = 0
        self.rem_themes: List[str] = []
        self.deep_promoted: List[str] = []
        self.deep_skipped: List[str] = []
        self.dream_narrative: str = ""  # REM phase free-form reflection

    def to_markdown(self) -> str:
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M UTC")
        lines = [f"## Dream Cycle — {ts}", ""]
        lines.append(f"**Light Sleep:** {self.light_count} candidates staged")
        lines.append("")
        if self.rem_themes:
            lines.append("**REM Themes:**")
            for t in self.rem_themes:
                lines.append(f"- {t}")
            lines.append("")
        if self.deep_promoted:
            lines.append(f"**Deep Sleep:** {len(self.deep_promoted)} memories promoted")
            for p in self.deep_promoted:
                lines.append(f"- {p}")
            lines.append("")
        if self.deep_skipped:
            lines.append(f"**Skipped (below threshold):** {len(self.deep_skipped)}")
            for s in self.deep_skipped:
                lines.append(f"- {s}")
            lines.append("")
        if self.dream_narrative:
            lines.append("**Dream Diary:**")
            lines.append(self.dream_narrative)
            lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _get_config() -> Dict[str, Any]:
    """Read dreaming config from config.yaml."""
    try:
        from hermes_cli.config import load_config, cfg_get
        config = load_config()
        dreaming_cfg = cfg_get(config, "plugins", "entries", "dreaming", "config") or {}
        return dreaming_cfg
    except Exception as e:
        logger.debug("Failed to read dreaming config: %s", e)
        return {}


def _config(key: str, default: Any = None) -> Any:
    cfg = _get_config()
    return cfg.get(key, default)


def is_enabled() -> bool:
    return bool(_config("enabled", True))


# ---------------------------------------------------------------------------
# Session store access
# ---------------------------------------------------------------------------


def _get_sessions_db_path() -> Path:
    """Return the path to the sessions SQLite database."""
    return get_hermes_home() / "sessions.db"


def _get_last_user_activity() -> Optional[datetime]:
    """Get the timestamp of the most recent user message across all sessions.

    Reads from the sessions.db SQLite store. Returns None if unavailable.
    This survives gateway restarts (persisted on disk).
    """
    db_path = _get_sessions_db_path()
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        # sessions table has updated_at; we want the max across all sessions
        row = conn.execute("SELECT MAX(updated_at) as last_active FROM sessions").fetchone()
        conn.close()
        if row and row["last_active"]:
            # updated_at is stored as ISO string or epoch depending on version
            ts = row["last_active"]
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            if isinstance(ts, str):
                try:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    pass
    except Exception as e:
        logger.debug("Failed to read last user activity: %s", e)
    return None


def _is_user_quiet(quiet_minutes: int = DEFAULT_QUIET_MINUTES) -> bool:
    """Check if the user has been inactive for at least quiet_minutes."""
    last_active = _get_last_user_activity()
    if last_active is None:
        return True  # no activity recorded, safe to dream
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=quiet_minutes)
    return last_active < cutoff


def _get_recent_sessions(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> List[Dict[str, Any]]:
    """Fetch recent session transcripts from the sessions database.

    Returns a list of dicts with keys: session_id, title, messages, updated_at.
    Only returns sessions updated within lookback_days.
    """
    db_path = _get_sessions_db_path()
    if not db_path.exists():
        return []

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=lookback_days)
    sessions = []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Get sessions updated within lookback window
        rows = conn.execute(
            "SELECT * FROM sessions WHERE updated_at > ? ORDER BY updated_at DESC",
            (cutoff.isoformat(),)
        ).fetchall()

        for row in rows:
            session_id = row["session_id"]
            # Get messages for this session
            msg_rows = conn.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,)
            ).fetchall()

            messages = []
            for m in msg_rows:
                content = m["content"]
                if isinstance(content, str) and len(content) > 500:
                    content = content[:500] + "…"
                messages.append({
                    "role": m["role"],
                    "content": content,
                    "created_at": m["created_at"],
                })

            if messages:
                sessions.append({
                    "session_id": session_id,
                    "title": row.get("title", session_id),
                    "messages": messages,
                    "updated_at": row["updated_at"],
                })

        conn.close()
    except Exception as e:
        logger.warning("Failed to read sessions for dreaming: %s", e)

    return sessions


# ---------------------------------------------------------------------------
# Memory file access
# ---------------------------------------------------------------------------


def _get_memory_dir() -> Path:
    return get_hermes_home()


def _get_dreams_path() -> Path:
    custom = _config("dream_diary_path")
    if custom:
        return Path(custom).expanduser().resolve()
    return _get_memory_dir() / "DREAMS.md"


def _get_memory_md_path() -> Path:
    return _get_memory_dir() / "MEMORY.md"


def _read_memory_md() -> str:
    p = _get_memory_md_path()
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    return ""


def _append_to_memory_md(entries: List[str]) -> None:
    """Append promoted entries to MEMORY.md."""
    if not entries:
        return
    p = _get_memory_md_path()
    existing = _read_memory_md()

    # Check for near-duplicates before appending
    existing_lines = set(existing.lower().splitlines())
    new_entries = []
    for entry in entries:
        entry_lower = entry.lower().strip()
        # Simple dedup: skip if a very similar line already exists
        is_dup = any(
            entry_lower in existing_line or existing_line in entry_lower
            for existing_line in existing_lines
            if len(existing_line) > 10
        )
        if not is_dup:
            new_entries.append(entry)
            existing_lines.add(entry_lower)

    if not new_entries:
        logger.debug("Dreaming: all promoted entries already exist in MEMORY.md")
        return

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    section = f"\n\n## Dreaming — {timestamp}\n" + "\n".join(f"- {e}" for e in new_entries) + "\n"

    if not existing.strip():
        content = f"# MEMORY.md — Long-Term Memory\n{section}"
    else:
        content = existing.rstrip() + "\n" + section

    p.write_text(content, encoding="utf-8")
    logger.info("Dreaming: wrote %d entries to MEMORY.md", len(new_entries))


def _append_to_dreams_md(entry: DreamDiaryEntry) -> None:
    """Append a dream diary entry to DREAMS.md."""
    p = _get_dreams_path()
    existing = ""
    if p.exists():
        existing = p.read_text(encoding="utf-8", errors="replace")

    md = entry.to_markdown()

    if not existing.strip():
        content = f"# DREAMS.md — Dream Diary\n\n{md}\n"
    else:
        content = existing.rstrip() + "\n" + md + "\n"

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    logger.info("Dreaming: wrote dream diary entry to %s", p)


# ---------------------------------------------------------------------------
# Light Sleep Phase — Sort, deduplicate, and stage candidates
# ---------------------------------------------------------------------------


# Noise patterns to filter out
_NOISE_PATTERNS = [
    re.compile(r"^(ok|yes|no|thanks|thank you|sure|got it|nice|cool|great|perfect|alright)\b", re.I),
    re.compile(r"^[\s\W]+$"),  # only whitespace/punctuation
    re.compile(r"^(http|https|www\.)", re.I),
    re.compile(r"^```"),  # code fences
    re.compile(r"^(>|#|\*|-|\d+\.)\s"),  # markdown formatting
    re.compile(r"^(error|warning|traceback|exception)\b", re.I),
    re.compile(r"^\[\[.*\]\]$"),  # directives like [[audio_as_voice]]
    re.compile(r"^MEDIA:"),  # media tags
    re.compile(r"^TICK_OK$|^HEARTBEAT_OK$", re.I),
]

# Minimum content to be a meaningful memory
_MIN_CONTENT_LENGTH = 20


def _is_noise(text: str) -> bool:
    """Check if a text fragment is noise (not worth remembering)."""
    if len(text) < _MIN_CONTENT_LENGTH:
        return True
    for pat in _NOISE_PATTERNS:
        if pat.match(text.strip()):
            return True
    return False


def _extract_candidates_from_sessions(
    sessions: List[Dict[str, Any]],
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> List[Candidate]:
    """Extract memory candidates from session transcripts (Light phase).

    Scans user messages and assistant responses for meaningful statements
    that could become long-term memories. Filters out noise, deduplicates,
    and counts frequency.
    """
    candidates: Dict[str, Candidate] = {}

    for session in sessions:
        for msg in session["messages"]:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue

            # Split into sentences/statements
            statements = re.split(r'(?<=[.!?])\s+|\n+', content)

            for stmt in statements:
                stmt = stmt.strip()
                if _is_noise(stmt):
                    continue

                # Normalize for dedup
                key = re.sub(r'\s+', ' ', stmt.lower().strip(' .!?,:;'))

                if key in candidates:
                    candidates[key].frequency += 1
                else:
                    if len(candidates) >= max_candidates:
                        continue
                    candidates[key] = Candidate(
                        text=stmt,
                        source=session.get("session_id", ""),
                        timestamp=datetime.now(tz=timezone.utc),
                    )

    # Sort by frequency (most mentioned first)
    result = sorted(candidates.values(), key=lambda c: c.frequency, reverse=True)
    return result


# ---------------------------------------------------------------------------
# REM Sleep Phase — Reflect on patterns and themes
# ---------------------------------------------------------------------------


def _run_rem_phase(
    candidates: List[Candidate],
    sessions: List[Dict[str, Any]],
) -> Tuple[List[str], str]:
    """Run the REM (reflection) phase.

    Identifies recurring themes across candidates and produces a narrative
    dream diary entry.

    Returns (themes, narrative).
    """
    themes: List[str] = []
    narrative = ""

    if not candidates:
        return themes, "No significant patterns detected this cycle."

    # Simple theme extraction: group candidates by shared keywords
    # In a more advanced version this could use an LLM call
    keyword_groups: Dict[str, List[Candidate]] = {}
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "here", "there", "when", "where", "why", "how", "all", "each",
        "every", "both", "few", "more", "most", "other", "some", "such", "no",
        "nor", "not", "only", "own", "same", "so", "than", "too", "very",
        "just", "because", "but", "and", "or", "if", "while", "about", "up",
        "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they",
        "this", "that", "these", "those", "what", "which", "who", "whom",
    }

    for c in candidates:
        words = re.findall(r'\b[a-z]{3,}\b', c.text.lower())
        for w in words:
            if w not in stop_words:
                keyword_groups.setdefault(w, []).append(c)

    # Themes are keywords that appear in multiple candidates
    for kw, group in sorted(keyword_groups.items(), key=lambda x: len(x[1]), reverse=True):
        if len(group) >= 2 and len(themes) < 10:
            themes.append(f"'{kw}' appeared across {len(group)} candidates")

    # Build a narrative summary
    top_candidates = candidates[:5]
    narrative_parts = [
        f"Reviewed {len(candidates)} memory candidates from {len(sessions)} recent sessions.",
        "",
        "Top recurring themes:",
    ]
    if themes:
        for t in themes[:5]:
            narrative_parts.append(f"  - {t}")
    else:
        narrative_parts.append("  - No strong recurring patterns this cycle.")

    narrative_parts.append("")
    narrative_parts.append("Most frequently mentioned:")
    for c in top_candidates[:3]:
        narrative_parts.append(f"  - {c.text[:120]}")

    narrative = "\n".join(narrative_parts)
    return themes, narrative


# ---------------------------------------------------------------------------
# Deep Sleep Phase — Score and promote
# ---------------------------------------------------------------------------


def _score_candidate(
    candidate: Candidate,
    total_candidates: int,
    existing_memory: str,
) -> float:
    """Score a memory candidate on multiple dimensions.

    Returns a float between 0 and 1.
    """
    breakdown: Dict[str, float] = {}

    # Relevance: does it contain meaningful keywords (not just chatter)?
    meaningful_words = len(re.findall(r'\b[a-z]{4,}\b', candidate.text.lower()))
    relevance = min(meaningful_words / 10.0, 1.0)
    breakdown["relevance"] = relevance * WEIGHT_RELEVANCE

    # Frequency: how many times did this topic appear?
    freq_score = min(candidate.frequency / 5.0, 1.0)
    breakdown["frequency"] = freq_score * WEIGHT_FREQUENCY

    # Query diversity: does it come from multiple sources?
    # (simplified: just use frequency as proxy)
    diversity = min(candidate.frequency / 3.0, 1.0)
    breakdown["query_diversity"] = diversity * WEIGHT_QUERY_DIVERSITY

    # Recency: newer is better
    age_days = (datetime.now(tz=timezone.utc) - candidate.timestamp).days
    recency = max(0, 1.0 - (age_days / DEFAULT_LOOKBACK_DAYS))
    breakdown["recency"] = recency * WEIGHT_RECENCY

    # Consolidation: penalize if similar to existing memory
    existing_lower = existing_memory.lower()
    text_lower = candidate.text.lower()
    # Check for significant overlap with existing memory
    overlap = 0
    for phrase in re.findall(r'\b[a-z]{4,}\b', text_lower):
        if phrase in existing_lower:
            overlap += 1
    consolidation = max(0, 1.0 - (overlap / max(meaningful_words, 1)))
    breakdown["consolidation"] = consolidation * WEIGHT_CONSOLIDATION

    # Conceptual richness: longer, more detailed = richer
    richness = min(len(candidate.text) / 200.0, 1.0)
    breakdown["conceptual_richness"] = richness * WEIGHT_CONCEPTUAL_RICHNESS

    total = sum(breakdown.values())
    candidate.score = total
    candidate.score_breakdown = breakdown
    return total


def _run_deep_phase(
    candidates: List[Candidate],
    existing_memory: str,
    threshold: float = DEFAULT_PROMOTION_THRESHOLD,
    min_recall: int = DEFAULT_MIN_RECALL_COUNT,
) -> Tuple[List[str], List[str]]:
    """Run the Deep (promotion) phase.

    Scores all candidates and promotes those above threshold to MEMORY.md.

    Returns (promoted_texts, skipped_texts).
    """
    promoted = []
    skipped = []

    for c in candidates:
        score = _score_candidate(c, len(candidates), existing_memory)

        if score >= threshold and c.frequency >= min_recall:
            promoted.append(c.text)
        else:
            skipped.append(f"{c.text[:80]} (score={score:.2f}, freq={c.frequency})")

    return promoted, skipped


# ---------------------------------------------------------------------------
# Main dreaming cycle
# ---------------------------------------------------------------------------


def run_dreaming_cycle(
    force: bool = False,
    verbose: bool = False,
) -> Optional[DreamDiaryEntry]:
    """Run a full dreaming cycle (Light → REM → Deep).

    Args:
        force: If True, skip the user-activity quiet check.
        verbose: If True, log detailed progress.

    Returns:
        DreamDiaryEntry if a cycle ran, None if skipped.
    """
    if not is_enabled() and not force:
        logger.debug("Dreaming is disabled in config")
        return None

    quiet_minutes = _config("quiet_minutes", DEFAULT_QUIET_MINUTES)
    if not force and not _is_user_quiet(quiet_minutes):
        logger.info(
            "Dreaming: user active within last %d minutes, skipping cycle",
            quiet_minutes,
        )
        return None

    lookback_days = _config("lookback_days", DEFAULT_LOOKBACK_DAYS)
    max_candidates = _config("max_candidates", DEFAULT_MAX_CANDIDATES)
    threshold = _config("promotion_threshold", DEFAULT_PROMOTION_THRESHOLD)
    min_recall = _config("min_recall_count", DEFAULT_MIN_RECALL_COUNT)

    logger.info("🌙 Dreaming cycle starting (lookback=%d days)", lookback_days)
    start_time = time.monotonic()

    diary = DreamDiaryEntry()

    # --- Light Sleep ---
    if verbose:
        logger.info("💤 Light Sleep: scanning recent sessions...")
    sessions = _get_recent_sessions(lookback_days)
    candidates = _extract_candidates_from_sessions(sessions, max_candidates)
    diary.light_count = len(candidates)
    logger.info("Light Sleep: staged %d candidates from %d sessions", len(candidates), len(sessions))

    if not candidates:
        logger.info("Dreaming: no candidates found, writing empty cycle")
        diary.dream_narrative = "No significant memories to consolidate this cycle."
        _append_to_dreams_md(diary)
        return diary

    # --- REM Sleep ---
    if verbose:
        logger.info("🌀 REM Sleep: reflecting on patterns...")
    themes, narrative = _run_rem_phase(candidates, sessions)
    diary.rem_themes = themes
    diary.dream_narrative = narrative
    logger.info("REM Sleep: found %d themes", len(themes))

    # --- Deep Sleep ---
    if verbose:
        logger.info("🛌 Deep Sleep: scoring and promoting...")
    existing_memory = _read_memory_md()
    promoted, skipped = _run_deep_phase(candidates, existing_memory, threshold, min_recall)
    diary.deep_promoted = promoted
    diary.deep_skipped = skipped

    if promoted:
        _append_to_memory_md(promoted)
        logger.info("Deep Sleep: promoted %d memories to MEMORY.md", len(promoted))
    else:
        logger.info("Deep Sleep: no memories promoted (threshold=%.2f)", threshold)

    # Write dream diary
    _append_to_dreams_md(diary)

    elapsed = time.monotonic() - start_time
    logger.info(
        "🌙 Dreaming cycle complete in %.1fs — %d staged, %d promoted",
        elapsed, len(candidates), len(promoted),
    )
    return diary


# ---------------------------------------------------------------------------
# Cron job management
# ---------------------------------------------------------------------------


def _build_cron_job() -> Dict[str, Any]:
    """Build the cron job configuration for the dreaming cycle."""
    frequency = _config("frequency", DEFAULT_FREQUENCY)
    return {
        "name": "Memory Dreaming Cycle",
        "schedule": frequency,
        "prompt": (
            "You are running the Dreaming memory consolidation cycle. "
            "This is an automated background task — do NOT send any messages to the user. "
            "Run the dreaming cycle by calling the dream_run tool with force=true. "
            "After the cycle completes, reply with DREAMING_DONE and a brief summary of what was consolidated."
        ),
        "enabled": True,
        "skills": ["dreaming"],
    }


def register_dreaming_cron() -> Optional[str]:
    """Register the dreaming cron job. Returns job ID or None."""
    try:
        from cron.jobs import add_job
        job = _build_cron_job()
        job_id = add_job(job)
        logger.info("Dreaming cron job registered: %s", job_id)
        return job_id
    except Exception as e:
        logger.warning("Failed to register dreaming cron job: %s", e)
        return None


def unregister_dreaming_cron() -> None:
    """Remove the dreaming cron job."""
    try:
        from cron.jobs import remove_job_by_name
        remove_job_by_name("Memory Dreaming Cycle")
        logger.info("Dreaming cron job removed")
    except Exception as e:
        logger.debug("Failed to remove dreaming cron job: %s", e)


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------


def register(ctx):
    """Register the dreaming plugin with Hermes."""
    if not is_enabled():
        logger.info("Dreaming plugin is disabled in config, skipping registration")
        return

    # Register the CLI command
    try:
        from plugins.dreaming.cli import register_cli
        register_cli(ctx)
    except Exception as e:
        logger.debug("Dreaming CLI registration: %s", e)

    # Register cron job
    register_dreaming_cron()

    logger.info("Dreaming plugin registered 🌙")
