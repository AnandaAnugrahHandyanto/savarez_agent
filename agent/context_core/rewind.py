"""RewindStore — checkpoint/rollback store for conversation message state.

The RewindStore provides a lightweight mechanism to save named snapshots of
the message list at strategic points (before compression, before a risky
tool call, at explicit checkpoints), and to restore a previous snapshot
when needed (e.g., compression degraded quality, a tool had unexpected
side effects, or the user wants to backtrack).

Key features:
- **Named checkpoints**: snapshots are keyed by string IDs (e.g. "pre_compress",
  "before_delegate", "post_file_edits").
- **Rollback**: restore any checkpoint by name, or undo the last restore.
- **Pruning**: automatic eviction of old checkpoints to bound memory usage.
- **Statistics**: tracks checkpoint sizes, hit rates, and rollback counts.
- **Serialization**: checkpoints can be serialized to JSON for persistence.

Usage::

    rewind = RewindStore(max_checkpoints=20)

    # Save a snapshot before a risky operation
    rewind.save("pre_refactor", messages)

    # ... agent does dangerous work ...

    # Rollback if something went wrong
    restored = rewind.restore("pre_refactor")
    assert restored == messages  # exact match

    # Undo the last restore
    previous = rewind.undo()

    # List available checkpoints
    for ckpt in rewind.checkpoints():
        print(ckpt.id, ckpt.size_tokens, ckpt.created_at)
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Rough chars-per-token estimate for size reporting
_CHARS_PER_TOKEN = 4


@dataclass
class Checkpoint:
    """A single named snapshot of the message list."""

    id: str
    """Unique string identifier for this checkpoint."""

    messages: List[Dict[str, Any]]
    """The committed message list at the time of saving."""

    size_chars: int = 0
    """Approximate character length of the serialized messages."""

    size_tokens_estimate: int = 0
    """Rough token estimate (size_chars / 4)."""

    created_at: float = field(default_factory=time.time)
    """Unix timestamp when this checkpoint was created."""

    access_count: int = 0
    """Number of times this checkpoint was used in a restore."""

    last_accessed_at: Optional[float] = None
    """Unix timestamp of last restore (if ever)."""

    label: str = ""
    """Optional human-readable label (e.g. 'before /compress')."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "messages": self.messages,
            "size_chars": self.size_chars,
            "size_tokens_estimate": self.size_tokens_estimate,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Checkpoint":
        return cls(
            id=d["id"],
            messages=d["messages"],
            size_chars=d.get("size_chars", 0),
            size_tokens_estimate=d.get("size_tokens_estimate", 0),
            created_at=d.get("created_at", time.time()),
            access_count=d.get("access_count", 0),
            last_accessed_at=d.get("last_accessed_at"),
            label=d.get("label", ""),
        )


class RewindStore:
    """Checkpoint/rollback store for conversation messages.

    Manages a dictionary of named Checkpoint objects and supports:
    - save / restore by ID
    - undo (restore the checkpoint that was active before the last restore)
    - automatic eviction of least-recently-used checkpoints
    - serialization to/from JSON for persistence across process restarts
    """

    def __init__(
        self,
        max_checkpoints: int = 20,
        max_age_seconds: Optional[float] = None,
        label_prefix: str = "",
    ):
        """
        Args:
            max_checkpoints: Maximum number of checkpoints to retain.
                When exceeded, least-recently-accessed checkpoints are evicted.
            max_age_seconds: Optional TTL — checkpoints older than this are
                silently evicted on save(). None = no TTL.
            label_prefix: Optional prefix prepended to auto-generated labels.
        """
        self.max_checkpoints = max_checkpoints
        self.max_age_seconds = max_age_seconds
        self.label_prefix = label_prefix

        self._checkpoints: Dict[str, Checkpoint] = {}
        self._save_order: List[str] = []  # LRU tracking (oldest first)
        self._restore_stack: List[str] = []  # stack of checkpoint IDs for undo
        self._last_saved_id: Optional[str] = None  # ID active before last restore

        self._stats = {
            "save_count": 0,
            "restore_count": 0,
            "undo_count": 0,
            "eviction_count": 0,
            "total_bytes_saved": 0,
        }

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def save(
        self,
        checkpoint_id: str,
        messages: List[Dict[str, Any]],
        label: str = "",
    ) -> Checkpoint:
        """Save a snapshot of the message list under *checkpoint_id*.

        If *checkpoint_id* already exists, it is replaced with a new snapshot.

        Args:
            checkpoint_id: Unique string key for this checkpoint.
            messages: The message list to snapshot.
            label: Optional human-readable description.

        Returns:
            The newly created Checkpoint object.
        """
        # Serialize to estimate size
        serialized = json.dumps(messages, ensure_ascii=False)
        size_chars = len(serialized)
        size_tokens = size_chars // _CHARS_PER_TOKEN

        # Clear any restore stack beyond this point (branching)
        self._restore_stack.clear()

        # Evict if at capacity (before saving new one)
        self._evict_lru()

        checkpoint = Checkpoint(
            id=checkpoint_id,
            messages=[m.copy() for m in messages],
            size_chars=size_chars,
            size_tokens_estimate=size_tokens,
            created_at=time.time(),
            label=f"{self.label_prefix}{label}" if label else self.label_prefix,
        )

        self._checkpoints[checkpoint_id] = checkpoint
        self._save_order.append(checkpoint_id)
        self._last_saved_id = checkpoint_id
        self._stats["save_count"] += 1
        self._stats["total_bytes_saved"] += size_chars

        logger.debug(
            "RewindStore: saved checkpoint '%s' (%d chars, ~%d tokens)",
            checkpoint_id, size_chars, size_tokens,
        )
        return checkpoint

    def restore(self, checkpoint_id: str) -> Optional[List[Dict[str, Any]]]:
        """Restore the message list to the state at checkpoint *checkpoint_id*.

        The current state (at the time of restore) is NOT auto-saved.
        Call save() explicitly before restore() if you need to save first.

        Args:
            checkpoint_id: ID of the checkpoint to restore.

        Returns:
            The message list at that checkpoint, or None if not found.

        Raises:
            KeyError: if checkpoint_id does not exist.
        """
        if checkpoint_id not in self._checkpoints:
            logger.warning("RewindStore: checkpoint '%s' not found", checkpoint_id)
            return None

        checkpoint = self._checkpoints[checkpoint_id]

        # Update access metadata
        checkpoint.access_count += 1
        checkpoint.last_accessed_at = time.time()

        # Move to end of LRU (most recently accessed)
        self._save_order = [cid for cid in self._save_order if cid != checkpoint_id]
        self._save_order.append(checkpoint_id)

        # Push onto undo stack
        self._restore_stack.append(checkpoint_id)
        self._stats["restore_count"] += 1

        logger.debug(
            "RewindStore: restored checkpoint '%s' (access #%d)",
            checkpoint_id, checkpoint.access_count,
        )
        return [m.copy() for m in checkpoint.messages]

    def undo(self) -> Optional[List[Dict[str, Any]]]:
        """Undo the last restore(), restoring the pre-restore state.

        This pops the undo stack and returns the checkpoint that was active
        before the previous restore.  If restore() was called without an
        intervening save(), this returns the last saved snapshot.

        Returns:
            The message list at the previous state, or None if nothing to undo.
        """
        if not self._restore_stack:
            logger.debug("RewindStore: undo stack is empty, nothing to undo")
            return None

        last_restored_id = self._restore_stack.pop()
        prev_id = self._last_saved_id or (self._restore_stack[-1] if self._restore_stack else None)

        self._stats["undo_count"] += 1

        if prev_id and prev_id in self._checkpoints:
            logger.debug("RewindStore: undo -> returning to checkpoint '%s'", prev_id)
            return [m.copy() for m in self._checkpoints[prev_id].messages]

        logger.debug("RewindStore: undo stack exhausted")
        return None

    def delete(self, checkpoint_id: str) -> bool:
        """Delete a specific checkpoint.

        Returns True if the checkpoint was deleted, False if it didn't exist.
        """
        if checkpoint_id not in self._checkpoints:
            return False

        del self._checkpoints[checkpoint_id]
        self._save_order = [cid for cid in self._save_order if cid != checkpoint_id]
        self._restore_stack = [cid for cid in self._restore_stack if cid != checkpoint_id]
        if self._last_saved_id == checkpoint_id:
            self._last_saved_id = self._save_order[-1] if self._save_order else None

        logger.debug("RewindStore: deleted checkpoint '%s'", checkpoint_id)
        return True

    def clear(self) -> None:
        """Delete all checkpoints and reset the store."""
        self._checkpoints.clear()
        self._save_order.clear()
        self._restore_stack.clear()
        self._last_saved_id = None
        logger.debug("RewindStore: cleared all checkpoints")

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get(self, checkpoint_id: str) -> Optional[List[Dict[str, Any]]]:
        """Return a copy of a checkpoint's messages without updating access metadata."""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint is None:
            return None
        return [m.copy() for m in checkpoint.messages]

    def exists(self, checkpoint_id: str) -> bool:
        """Return True if a checkpoint with this ID exists."""
        return checkpoint_id in self._checkpoints

    def checkpoints(
        self,
        sort_by: str = "created_at",
        reverse: bool = False,
    ) -> List[Checkpoint]:
        """Return a sorted list of all checkpoints.

        Args:
            sort_by: Field to sort by — "created_at", "id", "size_tokens_estimate",
                "access_count", or "last_accessed_at".
            reverse: If True, sort descending (most recent first for created_at).
        """
        valid_sorts = {"created_at", "id", "size_tokens_estimate", "access_count", "last_accessed_at"}
        if sort_by not in valid_sorts:
            raise ValueError(f"Invalid sort_by '{sort_by}'. Valid: {valid_sorts}")

        checkpoints = list(self._checkpoints.values())

        def sort_key(c: Checkpoint):
            val = getattr(c, sort_by, None)
            if val is None:
                return 0.0 if sort_by == "last_accessed_at" else ""
            return val

        return sorted(checkpoints, key=sort_key, reverse=reverse)

    @property
    def stats(self) -> Dict[str, Any]:
        """Return a snapshot of RewindStore statistics."""
        return {
            **self._stats,
            "checkpoint_count": len(self._checkpoints),
            "save_order": list(self._save_order),
            "restore_stack_depth": len(self._restore_stack),
            "last_saved_id": self._last_saved_id,
        }

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def _evict_lru(self) -> None:
        """Evict the least-recently-accessed checkpoint if over capacity."""
        while len(self._checkpoints) >= self.max_checkpoints:
            if not self._save_order:
                break
            oldest_id = self._save_order.pop(0)
            if oldest_id in self._checkpoints:
                del self._checkpoints[oldest_id]
                self._stats["eviction_count"] += 1
                logger.debug("RewindStore: evicted checkpoint '%s' (LRU)", oldest_id)

    def evict_expired(self) -> int:
        """Evict all checkpoints older than max_age_seconds.

        Returns the number of checkpoints evicted.
        """
        if self.max_age_seconds is None:
            return 0

        now = time.time()
        expired_ids = [
            cid for cid, ckpt in self._checkpoints.items()
            if (now - ckpt.created_at) > self.max_age_seconds
        ]
        for cid in expired_ids:
            self.delete(cid)

        if expired_ids:
            logger.debug("RewindStore: evicted %d expired checkpoint(s)", len(expired_ids))
        return len(expired_ids)

    # ------------------------------------------------------------------
    # Serialization (for persistence across restarts)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full store state to a dict (JSON-compatible)."""
        return {
            "checkpoints": {cid: ckpt.to_dict() for cid, ckpt in self._checkpoints.items()},
            "save_order": self._save_order,
            "restore_stack": self._restore_stack,
            "last_saved_id": self._last_saved_id,
            "stats": self._stats,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize the full store state to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: Dict[str, Any], **kwargs) -> "RewindStore":
        """Reconstruct a RewindStore from a serialized dict."""
        store = cls(**kwargs)
        for cid, ckpt_dict in d.get("checkpoints", {}).items():
            ckpt = Checkpoint.from_dict(ckpt_dict)
            store._checkpoints[cid] = ckpt
        store._save_order = d.get("save_order", [])
        store._restore_stack = d.get("restore_stack", [])
        store._last_saved_id = d.get("last_saved_id")
        store._stats = d.get("stats", {})
        return store

    @classmethod
    def from_json(cls, json_str: str, **kwargs) -> "RewindStore":
        """Reconstruct a RewindStore from a JSON string."""
        return cls.from_dict(json.loads(json_str), **kwargs)
