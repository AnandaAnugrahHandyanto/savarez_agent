"""
Rollback — Deterministic State Snapshots and Rollback for Sandboxes.

Implements copy-on-write snapshots for fast state capture and deterministic
reversion. Supports automatic rollback on dangerous operations and manual
trigger via API.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import hashlib
import logging
import threading
import time
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class RollbackAction(Enum):
    SNAPSHOT = "snapshot"
    ROLLBACK = "rollback"
    AUTO_ROLLBACK = "auto_rollback"
    COMMIT = "commit"


@dataclass
class Snapshot:
    """A point-in-time snapshot of sandbox state."""
    id: str
    sandbox_id: str
    root_path: str
    snapshot_path: str
    created_at: float = field(default_factory=time.time)
    size_bytes: int = 0
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sandbox_id": self.sandbox_id,
            "root_path": self.root_path,
            "snapshot_path": self.snapshot_path,
            "created_at": self.created_at,
            "size_bytes": self.size_bytes,
            "description": self.description,
            "metadata": self.metadata,
            "parent_id": self.parent_id,
        }


class RollbackManager:
    """
    Manages snapshots and rollbacks for sandbox instances.

    Features:
    - COW (copy-on-write) snapshots for efficiency
    - Automatic rollback on dangerous operations
    - Manual snapshot and rollback via API
    - Snapshot pruning and retention policies
    - Deterministic revert to clean state

    The rollback mechanism uses hard links for unchanged files to minimize
    storage overhead while maintaining complete isolation.
    """

    def __init__(self, sandbox_id: str, workspace_root: str):
        self.sandbox_id = sandbox_id
        self.workspace_root = workspace_root
        self._snapshots: Dict[str, Snapshot] = {}
        self._current_snapshot_id: Optional[str] = None
        self._snapshot_counter = 0
        self._lock = threading.RLock()
        self._snapshots_dir = os.path.join(workspace_root, ".snapshots")
        self._dangerous_patterns: List[Callable[[str], bool]] = []

        # Create snapshots directory
        os.makedirs(self._snapshots_dir, exist_ok=True)

        # Register default dangerous operation patterns
        self._register_dangerous_patterns()

    def _register_dangerous_patterns(self) -> None:
        """Register default patterns for dangerous operations."""
        dangerous = [
            lambda op: op in ("rm -rf", "rm -rf /", "rm -rf /*"),
            lambda op: "dd" in op and "of=" in op,
            lambda op: "mkfs" in op,
            lambda op: "fdisk" in op,
            lambda op: "> /dev/sd" in op,
            lambda op: "chmod 7777" in op or "chmod u+s" in op,
            lambda op: ":(){:|:&};:" in op,  # Fork bomb pattern
        ]
        self._dangerous_patterns.extend(dangerous)

    def is_dangerous(self, operation: str) -> bool:
        """Check if an operation is considered dangerous."""
        for pattern in self._dangerous_patterns:
            if pattern(operation):
                return True
        return False

    def add_dangerous_pattern(self, pattern: Callable[[str], bool]) -> None:
        """Add a custom dangerous operation pattern."""
        self._dangerous_patterns.append(pattern)

    def create_snapshot(self, description: str = "", auto: bool = False) -> str:
        """
        Create a point-in-time snapshot of the sandbox state.

        Args:
            description: Human-readable description
            auto: Whether this is an automatic snapshot

        Returns:
            Snapshot ID
        """
        with self._lock:
            self._snapshot_counter += 1
            snap_id = f"snap_{self.sandbox_id}_{self._snapshot_counter}_{int(time.time())}"

            snapshot_path = os.path.join(self._snapshots_dir, snap_id)
            os.makedirs(snapshot_path, exist_ok=True)

            # COW copy: use hard links for efficiency
            # Only copy files that have changed since last snapshot
            parent_path = None
            if self._current_snapshot_id and self._current_snapshot_id in self._snapshots:
                parent_path = self._snapshots[self._current_snapshot_id].snapshot_path

            total_size = self._copy_directory_cow(
                self.workspace_root,
                snapshot_path,
                parent_path,
            )

            snapshot = Snapshot(
                id=snap_id,
                sandbox_id=self.sandbox_id,
                root_path=self.workspace_root,
                snapshot_path=snapshot_path,
                description=description or ("auto" if auto else "manual"),
                size_bytes=total_size,
                parent_id=self._current_snapshot_id,
            )

            self._snapshots[snap_id] = snapshot
            self._current_snapshot_id = snap_id

            logger.info(f"Created snapshot {snap_id} for sandbox {self.sandbox_id}: {total_size} bytes")
            return snap_id

    def _copy_directory_cow(
        self,
        src: str,
        dst: str,
        parent_path: Optional[str] = None,
    ) -> int:
        """
        Copy directory with COW optimization.

        Files that exist in parent snapshot are hard-linked rather than copied.
        """
        total_size = 0

        if not os.path.exists(src):
            return 0

        for item in os.listdir(src):
            if item in (".snapshots", "__pycache__", ".git"):
                continue

            src_item = os.path.join(src, item)
            dst_item = os.path.join(dst, item)

            if os.path.isdir(src_item):
                os.makedirs(dst_item, exist_ok=True)
                total_size += self._copy_directory_cow(src_item, dst_item, parent_path)
            elif os.path.isfile(src_item):
                src_stat = os.stat(src_item)

                # Try to hard-link from parent if file unchanged
                if parent_path:
                    parent_item = os.path.join(parent_path, item)
                    if os.path.exists(parent_item):
                        parent_stat = os.stat(parent_item)
                        if (
                            src_stat.st_size == parent_stat.st_size
                            and src_stat.st_mtime == parent_stat.st_mtime
                            and src_stat.st_ino != parent_stat.st_ino
                        ):
                            try:
                                os.link(parent_item, dst_item)
                                continue
                            except OSError:
                                pass

                # Copy the file
                shutil.copy2(src_item, dst_item)
                total_size += src_stat.st_size

        return total_size

    def rollback(self, snapshot_id: Optional[str] = None) -> bool:
        """
        Rollback sandbox to a previous snapshot state.

        Args:
            snapshot_id: Target snapshot ID. If None, rolls back to previous.

        Returns:
            True if successful
        """
        with self._lock:
            if snapshot_id is None:
                # Roll back to parent of current
                if self._current_snapshot_id and self._current_snapshot_id in self._snapshots:
                    current = self._snapshots[self._current_snapshot_id]
                    snapshot_id = current.parent_id
                if not snapshot_id:
                    logger.warning(f"No snapshot to rollback to for sandbox {self.sandbox_id}")
                    return False

            if snapshot_id not in self._snapshots:
                logger.error(f"Snapshot {snapshot_id} not found for sandbox {self.sandbox_id}")
                return False

            target = self._snapshots[snapshot_id]
            if not os.path.exists(target.snapshot_path):
                logger.error(f"Snapshot path {target.snapshot_path} not found")
                return False

            # Restore state by copying from snapshot
            self._restore_from_snapshot(target.snapshot_path, self.workspace_root)

            self._current_snapshot_id = snapshot_id
            logger.info(f"Rolled back sandbox {self.sandbox_id} to snapshot {snapshot_id}")
            return True

    def _restore_from_snapshot(self, snapshot_path: str, target_path: str) -> None:
        """Restore workspace from snapshot."""
        # Clear non-snapshot directories in target
        for item in os.listdir(target_path):
            if item in (".snapshots", "__pycache__", ".git"):
                continue
            target_item = os.path.join(target_path, item)
            if os.path.isdir(target_item):
                shutil.rmtree(target_item, ignore_errors=True)
            elif os.path.exists(target_item):
                os.remove(target_item)

        # Copy from snapshot
        for item in os.listdir(snapshot_path):
            if item in (".snapshots", "__pycache__", ".git"):
                continue
            src_item = os.path.join(snapshot_path, item)
            dst_item = os.path.join(target_path, item)
            if os.path.isdir(src_item):
                shutil.copytree(src_item, dst_item)
            else:
                shutil.copy2(src_item, dst_item)

    def auto_snapshot(self, operation: str) -> Optional[str]:
        """
        Create an automatic snapshot before dangerous operations.

        Args:
            operation: The operation about to be performed

        Returns:
            Snapshot ID if created, None otherwise
        """
        if self.is_dangerous(operation):
            return self.create_snapshot(description=f"Auto snapshot before: {operation[:50]}", auto=True)
        return None

    def commit(self) -> bool:
        """
        Commit current state as the new baseline, discarding rollback history.

        Returns:
            True if successful
        """
        with self._lock:
            # Remove all snapshots except current
            current_id = self._current_snapshot_id
            if current_id and current_id in self._snapshots:
                current = self._snapshots[current_id]

                # Remove old snapshot directories
                for snap_id, snap in list(self._snapshots.items()):
                    if snap_id != current_id and os.path.exists(snap.snapshot_path):
                        shutil.rmtree(snap.snapshot_path, ignore_errors=True)

                self._snapshots = {current_id: current}
                self._snapshot_counter = 0
                logger.info(f"Committed snapshot {current_id} as new baseline")
                return True

            return False

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    def get_current_snapshot(self) -> Optional[Snapshot]:
        """Get current active snapshot."""
        if self._current_snapshot_id:
            return self._snapshots.get(self._current_snapshot_id)
        return None

    def list_snapshots(self) -> List[Snapshot]:
        """List all snapshots for this sandbox."""
        return sorted(self._snapshots.values(), key=lambda s: s.created_at)

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a specific snapshot."""
        with self._lock:
            if snapshot_id not in self._snapshots:
                return False

            snapshot = self._snapshots[snapshot_id]

            # Don't delete if it's the current or parent of current
            if snapshot_id == self._current_snapshot_id:
                logger.warning(f"Cannot delete current snapshot {snapshot_id}")
                return False

            # Remove snapshot directory
            if os.path.exists(snapshot.snapshot_path):
                shutil.rmtree(snapshot.snapshot_path, ignore_errors=True)

            del self._snapshots[snapshot_id]
            logger.info(f"Deleted snapshot {snapshot_id}")
            return True

    def prune_old_snapshots(self, keep_count: int = 5) -> int:
        """
        Prune old snapshots, keeping the most recent N.

        Args:
            keep_count: Number of recent snapshots to keep

        Returns:
            Number of snapshots deleted
        """
        with self._lock:
            snapshots = sorted(self._snapshots.values(), key=lambda s: s.created_at)
            deleted = 0

            for snapshot in snapshots[:-keep_count]:
                if snapshot.id != self._current_snapshot_id:
                    if self.delete_snapshot(snapshot.id):
                        deleted += 1

            return deleted

    def get_snapshot_diff(self, snapshot_id1: str, snapshot_id2: str) -> Dict[str, Any]:
        """
        Get diff between two snapshots.

        Returns:
            Dict with added, removed, modified files
        """
        if snapshot_id1 not in self._snapshots or snapshot_id2 not in self._snapshots:
            return {"error": "Snapshot not found"}

        snap1 = self._snapshots[snapshot_id1]
        snap2 = self._snapshots[snapshot_id2]

        files1 = self._get_all_files(snap1.snapshot_path)
        files2 = self._get_all_files(snap2.snapshot_path)

        added = files2 - files1
        removed = files1 - files2

        modified = set()
        for f in files1 & files2:
            if self._files_different(
                os.path.join(snap1.snapshot_path, f),
                os.path.join(snap2.snapshot_path, f),
            ):
                modified.add(f)

        return {
            "snapshot1": snapshot_id1,
            "snapshot2": snapshot_id2,
            "added": list(added),
            "removed": list(removed),
            "modified": list(modified),
        }

    def _get_all_files(self, root: str) -> set:
        """Get all files under root path, relative to root."""
        files = set()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in (".snapshots", "__pycache__", ".git")]
            for f in filenames:
                full_path = os.path.join(dirpath, f)
                rel_path = os.path.relpath(full_path, root)
                files.add(rel_path)
        return files

    def _files_different(self, path1: str, path2: str) -> bool:
        """Check if two files have different content."""
        try:
            with open(path1, "rb") as f1, open(path2, "rb") as f2:
                return f1.read() != f2.read()
        except IOError:
            return True

    def cleanup(self) -> None:
        """Clean up all snapshots for this sandbox."""
        with self._lock:
            for snapshot in self._snapshots.values():
                if os.path.exists(snapshot.snapshot_path):
                    shutil.rmtree(snapshot.snapshot_path, ignore_errors=True)
            self._snapshots.clear()
            self._current_snapshot_id = None
            logger.info(f"Cleaned up all snapshots for sandbox {self.sandbox_id}")
