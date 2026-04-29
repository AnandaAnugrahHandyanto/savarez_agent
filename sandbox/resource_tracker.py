"""
Resource Tracker — CPU, memory, disk usage monitoring and quota management.

Prevents resource exhaustion attacks by enforcing per-sandbox limits.
Lightweight implementation using psutil (optional) or os-based primitives.
"""

from __future__ import annotations

import os
import time
import threading
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    CPU_TIME = "cpu_time"       # seconds
    MEMORY = "memory"          # bytes
    DISK_READ = "disk_read"    # bytes
    DISK_WRITE = "disk_write"  # bytes
    PROCESS_COUNT = "process_count"


@dataclass
class ResourceQuota:
    """Per-sandbox resource quotas."""
    cpu_time_max: float = 300.0        # 5 minutes
    memory_max: int = 512 * 1024 * 1024  # 512 MB
    disk_read_max: int = 100 * 1024 * 1024  # 100 MB
    disk_write_max: int = 50 * 1024 * 1024   # 50 MB
    process_count_max: int = 50


@dataclass
class ResourceUsage:
    """Current resource usage snapshot."""
    cpu_time: float = 0.0
    memory: int = 0
    disk_read: int = 0
    disk_write: int = 0
    process_count: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_time": round(self.cpu_time, 2),
            "memory_mb": self.memory // (1024 * 1024),
            "disk_read_mb": self.disk_read // (1024 * 1024),
            "disk_write_mb": self.disk_write // (1024 * 1024),
            "process_count": self.process_count,
        }


class ResourceTracker:
    """
    Tracks resource usage for a sandbox and enforces quotas.

    Uses lightweight primitives (os.stat, /proc) without requiring psutil.
    Integrates with PolicyEngine for pre-execution quota checks.
    """

    def __init__(self, sandbox_id: str, quota: Optional[ResourceQuota] = None):
        self.sandbox_id = sandbox_id
        self.quota = quota or ResourceQuota()
        self._usage = ResourceUsage()
        self._lock = threading.RLock()
        self._start_time = time.time()
        self._enabled = True
        self._exceeded = False
        self._exceeded_reason: Optional[str] = None

    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def get_usage(self) -> ResourceUsage:
        """Get current resource usage snapshot."""
        with self._lock:
            self._update_usage()
            return self._usage

    def check_quota(self) -> tuple[bool, Optional[str]]:
        """
        Check if current usage exceeds quotas.
        Returns (allowed, reason).
        """
        if not self._enabled:
            return True, None

        with self._lock:
            self._update_usage()
            u = self._usage

        if u.cpu_time > self.quota.cpu_time_max:
            return False, f"CPU time exceeded: {u.cpu_time:.1f}s > {self.quota.cpu_time_max}s"
        if u.memory > self.quota.memory_max:
            return False, f"Memory exceeded: {u.memory // (1024*1024)}MB > {self.quota.memory_max // (1024*1024)}MB"
        if u.disk_read > self.quota.disk_read_max:
            return False, f"Disk read exceeded: {u.disk_read // (1024*1024)}MB > {self.quota.disk_read_max // (1024*1024)}MB"
        if u.disk_write > self.quota.disk_write_max:
            return False, f"Disk write exceeded: {u.disk_write // (1024*1024)}MB > {self.quota.disk_write_max // (1024*1024)}MB"
        if u.process_count > self.quota.process_count_max:
            return False, f"Process count exceeded: {u.process_count} > {self.quota.process_count_max}"

        return True, None

    def record_disk_write(self, bytes_count: int) -> None:
        """Record disk write operation."""
        with self._lock:
            self._usage.disk_write += bytes_count

    def record_disk_read(self, bytes_count: int) -> None:
        """Record disk read operation."""
        with self._lock:
            self._usage.disk_read += bytes_count

    def record_cpu_time(self, seconds: float) -> None:
        """Record CPU time used."""
        with self._lock:
            self._usage.cpu_time += seconds

    def _update_usage(self) -> None:
        """Update resource usage from system."""
        # CPU time: track elapsed since sandbox start
        self._usage.cpu_time = time.time() - self._start_time

        # Memory and process count via /proc/self/status
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        # Memory in kB
                        self._usage.memory = int(line.split()[1]) * 1024
                        break
        except (FileNotFoundError, IOError):
            # Not on Linux or /proc not accessible
            pass

        # Process count via subprocess
        try:
            result = subprocess.run(
                ["ps", "--ppid", str(os.getpid()), "-o", "pid=", "--no-headers"],
                capture_output=True, text=True, timeout=1
            )
            self._usage.process_count = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        self._usage.timestamp = time.time()

    def is_exhausted(self) -> tuple[bool, Optional[str]]:
        """Return True if any resource quota has been exceeded."""
        if self._exceeded:
            return True, self._exceeded_reason
        allowed, reason = self.check_quota()
        if not allowed:
            self._exceeded = True
            self._exceeded_reason = reason
        return not allowed, reason

    def reset(self) -> None:
        """Reset usage counters."""
        with self._lock:
            self._usage = ResourceUsage()
            self._start_time = time.time()
            self._exceeded = False
            self._exceeded_reason = None

    def summary(self) -> Dict[str, Any]:
        """Get resource usage summary."""
        usage = self.get_usage()
        within_quota, _ = self.check_quota()
        return {
            "sandbox_id": self.sandbox_id,
            "enabled": self._enabled,
            "quota_exceeded": not within_quota,
            "exceeded_reason": self._exceeded_reason,
            "usage": usage.to_dict(),
            "quota": {
                "cpu_time_max": self.quota.cpu_time_max,
                "memory_max_mb": self.quota.memory_max // (1024 * 1024),
                "disk_read_max_mb": self.quota.disk_read_max // (1024 * 1024),
                "disk_write_max_mb": self.quota.disk_write_max // (1024 * 1024),
                "process_count_max": self.quota.process_count_max,
            }
        }
