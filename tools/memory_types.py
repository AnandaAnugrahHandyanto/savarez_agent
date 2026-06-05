import json
import logging
import os
import tempfile
import hashlib
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set, List

from hermes_constants import get_hermes_home
from utils import atomic_replace

logger = logging.getLogger(__name__)

class MemoryType(str, Enum):
    USER_PREFERENCE = "user_preference"
    ENVIRONMENT = "environment"
    CONVENTION = "convention"
    FAILURE_PATTERN = "failure_pattern"
    TEMPORARY = "temporary"
    EPISODIC = "episodic"

@dataclass
class MemoryEntryMeta:
    entry_hash: str          # SHA256[:12] of content — stable key
    mem_type: str            # MemoryType value, default "environment"
    importance: float        # 0.0–1.0, default 0.5
    confidence: float        # 0.0–1.0, default 0.5
    created_at: str          # ISO8601 UTC
    last_accessed: str       # ISO8601 UTC, updated on retrieval
    retrieval_hits: int      # count of times surfaced
    expires_at: Optional[str]  # ISO8601 UTC or None

def get_memory_dir() -> Path:
    """Return the profile-scoped memories directory."""
    return get_hermes_home() / "memories"

class MetadataStore:
    def __init__(self, target: str):
        self.target = target
        self.path = self._path_for(target)
        self.meta: Dict[str, MemoryEntryMeta] = self.load()

    def _path_for(self, target: str) -> Path:
        mem_dir = get_memory_dir()
        if target == "user":
            return mem_dir / "USER.meta.json"
        return mem_dir / "MEMORY.meta.json"

    def load(self) -> Dict[str, MemoryEntryMeta]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {k: MemoryEntryMeta(**v) for k, v in data.items()}
        except Exception as e:
            logger.debug(f"Failed to load metadata for {self.target}: {e}")
            return {}

    def save(self) -> None:
        try:
            data = {k: asdict(v) for k, v in self.meta.items()}
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self.path.parent), suffix=".tmp", prefix=".meta_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                atomic_replace(tmp_path, self.path)
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.debug(f"Failed to save metadata for {self.target}: {e}")

    def upsert(self, entry: str, **kwargs) -> MemoryEntryMeta:
        entry_hash = hashlib.sha256(entry.encode("utf-8")).hexdigest()[:12]
        now = datetime.now(timezone.utc).isoformat()
        if entry_hash in self.meta:
            m = self.meta[entry_hash]
            m.last_accessed = now
            m.retrieval_hits += 1
            for k, v in kwargs.items():
                if v is not None:
                    setattr(m, k, v)
        else:
            self.meta[entry_hash] = MemoryEntryMeta(
                entry_hash=entry_hash,
                mem_type=kwargs.get("mem_type", MemoryType.ENVIRONMENT.value),
                importance=kwargs.get("importance", 0.5),
                confidence=kwargs.get("confidence", 0.5),
                created_at=now,
                last_accessed=now,
                retrieval_hits=0,
                expires_at=kwargs.get("expires_at"),
            )
        self.save()
        return self.meta[entry_hash]

    def remove(self, entry: str) -> None:
        entry_hash = hashlib.sha256(entry.encode("utf-8")).hexdigest()[:12]
        if entry_hash in self.meta:
            del self.meta[entry_hash]
            self.save()

    def get(self, entry_hash: str) -> Optional[MemoryEntryMeta]:
        return self.meta.get(entry_hash)

    def bump_retrieval(self, entry_hash: str) -> None:
        m = self.meta.get(entry_hash)
        if m:
            m.retrieval_hits += 1
            m.last_accessed = datetime.now(timezone.utc).isoformat()
            self.save()

    def purge_orphans(self, valid_entries: List[str]) -> None:
        valid_hashes = {hashlib.sha256(e.encode("utf-8")).hexdigest()[:12] for e in valid_entries}
        initial_len = len(self.meta)
        self.meta = {k: v for k, v in self.meta.items() if k in valid_hashes}
        
        # Give legacy entries default metadata
        for e in valid_entries:
            eh = hashlib.sha256(e.encode("utf-8")).hexdigest()[:12]
            if eh not in self.meta:
                now = datetime.now(timezone.utc).isoformat()
                self.meta[eh] = MemoryEntryMeta(
                    entry_hash=eh,
                    mem_type=MemoryType.USER_PREFERENCE.value if self.target == "user" else MemoryType.ENVIRONMENT.value,
                    importance=0.5,
                    confidence=0.5,
                    created_at=now,
                    last_accessed=now,
                    retrieval_hits=0,
                    expires_at=None,
                )
        
        if len(self.meta) != initial_len or any(h not in valid_hashes for h in self.meta):
            self.save()
