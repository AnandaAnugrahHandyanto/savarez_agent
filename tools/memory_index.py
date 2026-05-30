"""Local tiered/vector index for built-in Hermes memory files.

This module is intentionally dependency-light: it uses SQLite plus a small
hashed bag-of-words embedding so memory recall can be ranked semantically-ish
without requiring a network embedding provider or sqlite-vss.  Future backends
can replace ``HashedEmbeddingBackend`` behind the same public functions.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from hermes_constants import get_hermes_home
from tools.memory_tool import ENTRY_DELIMITER
from tools.threat_patterns import scan_for_threats

_TIERS = ("hot", "warm", "cold")
_TARGET_FILES = {"memory": "MEMORY.md", "user": "USER.md"}
_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-]{1,}")
_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|bearer\s+[A-Za-z0-9._\-]{16,}|sk-[A-Za-z0-9]{16,})"
)


@dataclass(frozen=True)
class MemoryIndexConfig:
    enabled: bool = False
    dim: int = 128
    hot_limit: int = 8
    warm_limit: int = 12
    cross_profile_enabled: bool = False
    authorized_profiles: tuple[str, ...] = ()
    cold_min_score: float = 0.72
    db_path: str = ""

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> "MemoryIndexConfig":
        memory_cfg = (config or {}).get("memory", {}) if isinstance(config, dict) else {}
        tiered = memory_cfg.get("tiered", {}) if isinstance(memory_cfg, dict) else {}
        if not isinstance(tiered, dict):
            tiered = {}
        profiles = tiered.get("authorized_profiles", [])
        if isinstance(profiles, str):
            profiles = [p.strip() for p in profiles.split(",") if p.strip()]
        elif not isinstance(profiles, list):
            profiles = []
        return cls(
            enabled=bool(tiered.get("enabled", False)),
            dim=int(tiered.get("embedding_dim", 128) or 128),
            hot_limit=int(tiered.get("hot_limit", 8) or 8),
            warm_limit=int(tiered.get("warm_limit", 12) or 12),
            cross_profile_enabled=bool(tiered.get("cross_profile_enabled", False)),
            authorized_profiles=tuple(str(p) for p in profiles),
            cold_min_score=float(tiered.get("cold_min_score", 0.72) or 0.72),
            db_path=str(tiered.get("db_path", "") or ""),
        )


def index_path(hermes_home: Path | None = None, cfg: MemoryIndexConfig | None = None) -> Path:
    if cfg and cfg.db_path:
        return Path(os.path.expanduser(cfg.db_path))
    home = hermes_home or get_hermes_home()
    return home / "memories" / "memory_index.sqlite3"


class HashedEmbeddingBackend:
    """Deterministic local embedding fallback with no external dependencies."""

    def __init__(self, dim: int = 128) -> None:
        self.dim = max(16, int(dim or 128))

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dim
            sign = -1.0 if digest[4] & 1 else 1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm:
            vec = [round(v / norm, 6) for v in vec]
        return vec


def _tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def _entry_hash(profile: str, target: str, content: str) -> str:
    data = f"{profile}\0{target}\0{content}".encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def is_sensitive_memory(content: str) -> bool:
    """Return true if content should not be indexed/injected from aggregate search."""
    if not content:
        return False
    return bool(_SECRET_RE.search(content) or scan_for_threats(content, scope="strict"))


def _read_memory_entries(mem_dir: Path, target: str) -> list[str]:
    path = mem_dir / _TARGET_FILES[target]
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    entries = [e.strip() for e in text.split(ENTRY_DELIMITER) if e.strip()]
    return list(dict.fromkeys(entries))


def _profile_home(root_home: Path, profile: str) -> Path:
    if profile == "default":
        return root_home.parent.parent if root_home.parent.name == "profiles" else root_home
    if root_home.parent.name == "profiles":
        return root_home.parent / profile
    return root_home / "profiles" / profile


def _active_profile_name(hermes_home: Path) -> str:
    if hermes_home.parent.name == "profiles":
        return hermes_home.name
    return "default"


def _profile_allowed(profile: str, active_profile: str, cfg: MemoryIndexConfig) -> bool:
    """Enforce profile isolation for every index read/write path."""
    if profile == active_profile:
        return True
    if not cfg.cross_profile_enabled:
        return False
    # Cross-profile access must be explicitly bounded.  An empty allowlist means
    # no non-active profiles are authorized, not "all profiles".
    return profile in set(cfg.authorized_profiles)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS memory_index_entries (
            id TEXT PRIMARY KEY,
            profile TEXT NOT NULL,
            namespace TEXT NOT NULL DEFAULT '',
            target TEXT NOT NULL,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            tier TEXT NOT NULL CHECK(tier IN ('hot','warm','cold')),
            sensitivity TEXT NOT NULL DEFAULT 'normal',
            use_count INTEGER NOT NULL DEFAULT 0,
            relevance REAL NOT NULL DEFAULT 0,
            last_used_at REAL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            embedding TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memory_index_profile_tier
            ON memory_index_entries(profile, namespace, tier);
        CREATE INDEX IF NOT EXISTS idx_memory_index_content_hash
            ON memory_index_entries(content_hash);
        CREATE TABLE IF NOT EXISTS memory_index_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    conn.commit()


def rebuild_index(
    *,
    hermes_home: Path | None = None,
    profiles: Sequence[str] | None = None,
    namespace: str = "",
    cfg: MemoryIndexConfig | None = None,
) -> dict[str, Any]:
    """Rebuild index rows from MEMORY.md/USER.md without mutating source files."""
    home = hermes_home or get_hermes_home()
    cfg = cfg or MemoryIndexConfig()
    active_profile = _active_profile_name(home)
    selected_profiles = tuple(profiles or (active_profile,))
    embedder = HashedEmbeddingBackend(cfg.dim)
    now = time.time()
    scanned = indexed = skipped_sensitive = 0
    processed_profiles: list[str] = []

    with connect(index_path(home, cfg)) as conn:
        for profile in selected_profiles:
            if not _profile_allowed(profile, active_profile, cfg):
                continue
            processed_profiles.append(profile)
            mem_dir = _profile_home(home, profile) / "memories"
            for target in _TARGET_FILES:
                current_ids: set[str] = set()
                for entry in _read_memory_entries(mem_dir, target):
                    scanned += 1
                    entry_id = _entry_hash(profile, target, entry)
                    current_ids.add(entry_id)
                    sensitive = is_sensitive_memory(entry)
                    if sensitive:
                        skipped_sensitive += 1
                        # Remove any stale cleartext copy from an older index build.
                        conn.execute(
                            "DELETE FROM memory_index_entries WHERE id = ?",
                            (entry_id,),
                        )
                        continue
                    existing = conn.execute(
                        "SELECT tier, use_count, last_used_at, relevance, created_at, updated_at FROM memory_index_entries WHERE id = ?",
                        (entry_id,),
                    ).fetchone()
                    tier = existing["tier"] if existing else "warm"
                    use_count = int(existing["use_count"] if existing else 0)
                    last_used_at = existing["last_used_at"] if existing else None
                    relevance = float(existing["relevance"] if existing else 0.0)
                    created_at = float(existing["created_at"] if existing else now)
                    updated_at = float(existing["updated_at"] if existing and "updated_at" in existing.keys() else now)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO memory_index_entries
                          (id, profile, namespace, target, content, content_hash, tier,
                           sensitivity, use_count, relevance, last_used_at, created_at,
                           updated_at, embedding)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'normal', ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entry_id,
                            profile,
                            namespace,
                            target,
                            entry,
                            _content_hash(entry),
                            tier,
                            use_count,
                            relevance,
                            last_used_at,
                            created_at,
                            updated_at,
                            json.dumps(embedder.embed(entry)),
                        ),
                    )
                    indexed += 1
                # A rebuild is also a privacy purge: remove rows for entries
                # deleted, edited, or newly classified as sensitive in source.
                if current_ids:
                    placeholders = ",".join("?" for _ in current_ids)
                    conn.execute(
                        f"""
                        DELETE FROM memory_index_entries
                        WHERE profile = ? AND namespace = ? AND target = ?
                          AND id NOT IN ({placeholders})
                        """,
                        (profile, namespace, target, *current_ids),
                    )
                else:
                    conn.execute(
                        """
                        DELETE FROM memory_index_entries
                        WHERE profile = ? AND namespace = ? AND target = ?
                        """,
                        (profile, namespace, target),
                    )
        conn.execute(
            "INSERT OR REPLACE INTO memory_index_meta(key, value) VALUES ('last_rebuild_at', ?)",
            (str(now),),
        )
        conn.commit()
    return {
        "profiles": processed_profiles,
        "scanned": scanned,
        "indexed": indexed,
        "skipped_sensitive": skipped_sensitive,
        "db_path": str(index_path(home, cfg)),
    }


def search_index(
    query: str,
    *,
    hermes_home: Path | None = None,
    profile: str | None = None,
    namespace: str = "",
    limit: int = 10,
    include_cold: bool = False,
    record_usage: bool = True,
    cfg: MemoryIndexConfig | None = None,
) -> list[dict[str, Any]]:
    home = hermes_home or get_hermes_home()
    cfg = cfg or MemoryIndexConfig()
    profile = profile or _active_profile_name(home)
    active_profile = _active_profile_name(home)
    if not _profile_allowed(profile, active_profile, cfg):
        return []
    embedder = HashedEmbeddingBackend(cfg.dim)
    qvec = embedder.embed(query)
    qtokens = set(_tokens(query))
    tiers = ("hot", "warm", "cold") if include_cold else ("hot", "warm")
    per_tier_limit = {"hot": cfg.hot_limit, "warm": cfg.warm_limit, "cold": max(limit, cfg.warm_limit)}
    rows: list[dict[str, Any]] = []
    now = time.time()
    with connect(index_path(home, cfg)) as conn:
        for tier in tiers:
            fetched = conn.execute(
                """
                SELECT * FROM memory_index_entries
                WHERE profile = ? AND namespace = ? AND tier = ? AND sensitivity = 'normal'
                """,
                (profile, namespace, tier),
            ).fetchall()
            scored: list[tuple[float, sqlite3.Row]] = []
            for row in fetched:
                emb = json.loads(row["embedding"] or "[]")
                semantic = _cosine(qvec, emb)
                rtokens = set(_tokens(row["content"]))
                exact = len(qtokens & rtokens) / max(1, len(qtokens))
                age_days = (now - float(row["last_used_at"] or row["updated_at"] or now)) / 86400.0
                recency = 1.0 / (1.0 + max(0.0, age_days) / 30.0)
                frequency = math.log1p(int(row["use_count"] or 0)) / 5.0
                tier_boost = {"hot": 0.18, "warm": 0.06, "cold": -0.04}[tier]
                score = (semantic * 0.52) + (exact * 0.25) + (recency * 0.12) + frequency + tier_boost
                min_score = 0.20 if tier != "cold" else cfg.cold_min_score
                if score >= min_score:
                    scored.append((score, row))
            scored.sort(key=lambda x: x[0], reverse=True)
            for score, row in scored[:per_tier_limit[tier]]:
                rows.append({
                    "id": row["id"],
                    "profile": row["profile"],
                    "target": row["target"],
                    "tier": row["tier"],
                    "score": round(score, 4),
                    "content": row["content"],
                })
            if len(rows) >= limit:
                break
        rows = rows[:limit]
        if record_usage and rows:
            hit_ids = [row["id"] for row in rows]
            conn.executemany(
                """
                UPDATE memory_index_entries
                SET use_count = use_count + 1, last_used_at = ?, relevance = MAX(relevance, ?)
                WHERE id = ?
                """,
                [(now, float(row["score"]), row_id) for row, row_id in zip(rows, hit_ids)],
            )
            conn.commit()
    return rows


def dream_index(
    *,
    hermes_home: Path | None = None,
    apply: bool = False,
    cfg: MemoryIndexConfig | None = None,
) -> dict[str, Any]:
    """Review indexed rows and propose/apply non-destructive tier changes."""
    home = hermes_home or get_hermes_home()
    cfg = cfg or MemoryIndexConfig()
    now = time.time()
    proposals: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    active_profile = _active_profile_name(home)
    allowed_profiles = [active_profile, *cfg.authorized_profiles] if cfg.cross_profile_enabled else [active_profile]
    # Deduplicate while preserving order; active profile is always first.
    allowed_profiles = list(dict.fromkeys(p for p in allowed_profiles if _profile_allowed(p, active_profile, cfg)))
    with connect(index_path(home, cfg)) as conn:
        placeholders = ",".join("?" for _ in allowed_profiles)
        rows = conn.execute(
            f"SELECT * FROM memory_index_entries WHERE sensitivity = 'normal' AND profile IN ({placeholders})",
            tuple(allowed_profiles),
        ).fetchall()
        seen: dict[str, sqlite3.Row] = {}
        for row in rows:
            age_days = (now - float(row["last_used_at"] or row["updated_at"] or now)) / 86400.0
            use_count = int(row["use_count"] or 0)
            if use_count >= 5 or age_days <= 14:
                desired = "hot"
            elif use_count >= 1 or age_days <= 90:
                desired = "warm"
            else:
                desired = "cold"
            if desired != row["tier"]:
                proposals.append({"id": row["id"], "from": row["tier"], "to": desired, "content_preview": row["content"][:120]})
                if apply:
                    conn.execute("UPDATE memory_index_entries SET tier = ?, updated_at = ? WHERE id = ?", (desired, now, row["id"]))
            if age_days > 180 and use_count == 0:
                stale.append({"id": row["id"], "tier": row["tier"], "content_preview": row["content"][:120]})
            ch = row["content_hash"]
            if ch in seen:
                duplicates.append({
                    "keep_id": seen[ch]["id"],
                    "duplicate_id": row["id"],
                    "content_preview": row["content"][:120],
                })
            else:
                seen[ch] = row
        if apply:
            conn.execute("INSERT OR REPLACE INTO memory_index_meta(key, value) VALUES ('last_dream_at', ?)", (str(now),))
            conn.commit()
    return {
        "apply": apply,
        "tier_changes": proposals,
        "duplicates": duplicates,
        "stale_candidates": stale,
        "note": "Dreaming never deletes or rewrites MEMORY.md/USER.md; duplicates/stale entries are reports for human review.",
    }


def index_status(*, hermes_home: Path | None = None, cfg: MemoryIndexConfig | None = None) -> dict[str, Any]:
    home = hermes_home or get_hermes_home()
    cfg = cfg or MemoryIndexConfig()
    path = index_path(home, cfg)
    if not path.exists():
        return {"enabled": cfg.enabled, "db_path": str(path), "exists": False, "counts": {}}
    active_profile = _active_profile_name(home)
    allowed_profiles = [active_profile, *cfg.authorized_profiles] if cfg.cross_profile_enabled else [active_profile]
    allowed_profiles = list(dict.fromkeys(p for p in allowed_profiles if _profile_allowed(p, active_profile, cfg)))
    with connect(path) as conn:
        placeholders = ",".join("?" for _ in allowed_profiles)
        counts = {
            f"{row['profile']}:{row['tier']}": int(row["n"])
            for row in conn.execute(
                f"""
                SELECT profile, tier, COUNT(*) AS n
                FROM memory_index_entries
                WHERE profile IN ({placeholders})
                GROUP BY profile, tier
                """,
                tuple(allowed_profiles),
            )
        }
        meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM memory_index_meta")}
    return {"enabled": cfg.enabled, "db_path": str(path), "exists": True, "counts": counts, "meta": meta}
