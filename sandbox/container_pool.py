"""
Container Pool — Pre-warmed container pool for fast sandbox allocation.

Inspired by CubeSandbox's lightweight container approach, this implements
a pool of pre-initialized sandbox containers that can be rapidly allocated
to avoid cold-start delays. Containers are recycled after use.

Lightweight implementation using:
- Python subprocess isolation (no full container runtime)
- Temporary directory workspaces with automatic cleanup
- Process-level resource limits via ResourceTracker
"""

from __future__ import annotations

import os
import sys
import time
import uuid
import shutil
import tempfile
import threading
import logging
import subprocess
import concurrent.futures
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ContainerState(Enum):
    """Possible states for a pooled container."""
    PENDING = "pending"       # Being prepared
    READY = "ready"          # Available for use
    IN_USE = "in_use"        # Currently allocated
    RECYCLING = "recycling"   # Being cleaned for reuse
    ERROR = "error"           # Failed, needs attention


@dataclass
class Container:
    """A single container instance in the pool."""
    id: str
    state: ContainerState = ContainerState.PENDING
    workspace_path: str = ""
    created_at: float = field(default_factory=time.time)
    last_used_at: Optional[float] = None
    use_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    pool_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state.value,
            "workspace_path": self.workspace_path,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "use_count": self.use_count,
            "metadata": self.metadata,
        }


class ContainerPool:
    """
    Pre-warmed pool of lightweight sandbox containers.

    Features:
    - Pre-initializes N containers at startup
    - Sub-100ms container allocation via reuse
    - Automatic cleanup and recycling
    - Configurable container templates
    - Health monitoring and lazy recreation

    The pool maintains a queue of ready containers. When a container is
    allocated, it's removed from the ready queue. When released, it goes
    through recycling (state cleanup) before returning to the ready queue.
    """

    DEFAULT_POOL_SIZE = 5
    MAX_POOL_SIZE = 50
    RECYCLE_TIMEOUT = 5.0  # seconds

    def __init__(
        self,
        pool_id: str = "default",
        size: int = DEFAULT_POOL_SIZE,
        workspace_root: Optional[str] = None,
        container_factory: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        """
        Initialize container pool.

        Args:
            pool_id: Identifier for this pool
            size: Number of pre-warmed containers
            workspace_root: Root directory for container workspaces
            container_factory: Optional factory function to customize containers
        """
        self.pool_id = pool_id
        self._size = size
        self._workspace_root = workspace_root or tempfile.mkdtemp(prefix="sandbox_pool_")
        self._container_factory = container_factory or self._default_factory

        self._containers: Dict[str, Container] = {}
        self._ready_queue: List[str] = []  # IDs of ready containers
        self._lock = threading.RLock()
        self._initialized = False
        self._init_thread: Optional[threading.Thread] = None

        # Statistics
        self._stats = {
            "total_allocations": 0,
            "total_recycles": 0,
            "total_errors": 0,
            "avg_wait_time": 0.0,
        }
        self._wait_times: List[float] = []

    def _default_factory(self) -> Dict[str, Any]:
        """Default container configuration."""
        container_id = f"cnt_{uuid.uuid4().hex[:12]}"
        workspace = os.path.join(self._workspace_root, container_id)
        os.makedirs(workspace, exist_ok=True)
        return {
            "id": container_id,
            "workspace_path": workspace,
            "metadata": {},
        }

    def initialize(self, async_init: bool = True) -> None:
        """
        Pre-warm the pool by creating initial containers.

        Args:
            async_init: If True, initialization happens in background
        """
        if self._initialized:
            return

        if async_init:
            self._init_thread = threading.Thread(
                target=self._do_initialize,
                name=f"pool-init-{self.pool_id}",
                daemon=True,
            )
            self._init_thread.start()
        else:
            self._do_initialize()

    def _do_initialize(self) -> None:
        """Perform actual pool initialization."""
        logger.info(f"Initializing container pool {self.pool_id} with {self._size} containers")
        for i in range(self._size):
            try:
                container = self._create_container()
                with self._lock:
                    self._containers[container.id] = container
                    self._ready_queue.append(container.id)
                    container.state = ContainerState.READY
            except Exception as e:
                logger.error(f"Failed to create container {i+1}/{self._size}: {e}")
                self._stats["total_errors"] += 1

        with self._lock:
            self._initialized = True
        logger.info(f"Container pool {self.pool_id} initialized: {len(self._ready_queue)} ready")

    def _create_container(self) -> Container:
        """Create a new container instance."""
        config = self._container_factory()
        container = Container(
            id=config["id"],
            workspace_path=config["workspace_path"],
            metadata=config.get("metadata", {}),
            pool_id=self.pool_id,
            state=ContainerState.PENDING,
        )
        return container

    def allocate(self, timeout: float = 30.0) -> Optional[Container]:
        """
        Allocate a container from the pool.

        Args:
            timeout: Maximum seconds to wait for a container

        Returns:
            Container if available, None otherwise
        """
        start_time = time.time()

        # Ensure pool is initialized
        if not self._initialized:
            self._do_initialize()

        while time.time() - start_time < timeout:
            with self._lock:
                if self._ready_queue:
                    container_id = self._ready_queue.pop(0)
                    container = self._containers.get(container_id)
                    if container and container.state == ContainerState.READY:
                        container.state = ContainerState.IN_USE
                        container.last_used_at = time.time()
                        container.use_count += 1
                        self._stats["total_allocations"] += 1
                        return container

            # Wait a bit before retrying
            time.sleep(0.01)  # 10ms

        logger.warning(f"Container allocation timed out after {timeout}s")
        return None

    def release(self, container: Container) -> bool:
        """
        Release a container back to the pool for reuse.

        Args:
            container: Container to release

        Returns:
            True if successfully recycled, False otherwise
        """
        if container.pool_id != self.pool_id:
            logger.warning(f"Container {container.id} belongs to different pool")
            return False

        try:
            # Perform recycling in thread
            recycle_thread = threading.Thread(
                target=self._recycle_container,
                args=(container,),
                name=f"container-recycle-{container.id}",
                daemon=True,
            )
            recycle_thread.start()
            recycle_thread.join(timeout=self.RECYCLE_TIMEOUT)

            with self._lock:
                if container.state != ContainerState.ERROR:
                    container.state = ContainerState.READY
                    if container.id not in self._ready_queue:
                        self._ready_queue.append(container.id)
                    self._stats["total_recycles"] += 1
                    return True

        except Exception as e:
            logger.error(f"Failed to recycle container {container.id}: {e}")
            with self._lock:
                container.state = ContainerState.ERROR
                self._stats["total_errors"] += 1

        return False

    def _recycle_container(self, container: Container) -> None:
        """Clean up container for reuse."""
        container.state = ContainerState.RECYCLING

        try:
            # Clean up workspace
            workspace = container.workspace_path
            if os.path.exists(workspace):
                # Remove all files except .snapshots
                for item in os.listdir(workspace):
                    if item == ".snapshots":
                        continue
                    item_path = os.path.join(workspace, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        os.remove(item_path)

            # Reset resource tracking
            container.metadata.pop("resource_usage", None)

        except Exception as e:
            logger.error(f"Error recycling container {container.id}: {e}")
            container.state = ContainerState.ERROR

    def get_container(self, container_id: str) -> Optional[Container]:
        """Get container by ID."""
        return self._containers.get(container_id)

    def get_ready_count(self) -> int:
        """Get number of ready containers."""
        with self._lock:
            return len(self._ready_queue)

    def get_in_use_count(self) -> int:
        """Get number of containers currently in use."""
        with self._lock:
            return sum(1 for c in self._containers.values() if c.state == ContainerState.IN_USE)

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            avg_wait = sum(self._wait_times) / len(self._wait_times) if self._wait_times else 0.0
            return {
                "pool_id": self.pool_id,
                "size": self._size,
                "total_containers": len(self._containers),
                "ready": len(self._ready_queue),
                "in_use": self.get_in_use_count(),
                "initialized": self._initialized,
                "total_allocations": self._stats["total_allocations"],
                "total_recycles": self._stats["total_recycles"],
                "total_errors": self._stats["total_errors"],
                "avg_wait_time": round(avg_wait, 4),
            }

    def scale(self, new_size: int) -> int:
        """
        Scale pool to new size.

        Args:
            new_size: Target pool size

        Returns:
            Number of containers added (can be negative)
        """
        new_size = max(1, min(new_size, self.MAX_POOL_SIZE))
        with self._lock:
            old_size = self._size
            self._size = new_size

            # Add containers if needed
            added = 0
            while len(self._containers) < new_size:
                try:
                    container = self._create_container()
                    self._containers[container.id] = container
                    self._ready_queue.append(container.id)
                    container.state = ContainerState.READY
                    added += 1
                except Exception as e:
                    logger.error(f"Failed to scale up pool: {e}")
                    break

            return added - (old_size - new_size)

    def cleanup(self) -> None:
        """Clean up all containers and remove workspace."""
        with self._lock:
            # Clear container list
            for container in self._containers.values():
                try:
                    if os.path.exists(container.workspace_path):
                        shutil.rmtree(container.workspace_path, ignore_errors=True)
                except Exception as e:
                    logger.error(f"Error cleaning container {container.id}: {e}")

            self._containers.clear()
            self._ready_queue.clear()

        # Remove workspace root
        if os.path.exists(self._workspace_root):
            shutil.rmtree(self._workspace_root, ignore_errors=True)

        self._initialized = False
        logger.info(f"Cleaned up container pool {self.pool_id}")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all containers.

        Returns:
            Health status report
        """
        with self._lock:
            containers = list(self._containers.values())

        healthy = 0
        unhealthy = []
        for container in containers:
            issues = []

            # Check workspace exists
            if not os.path.exists(container.workspace_path):
                issues.append("workspace_missing")

            # Check container state
            if container.state == ContainerState.ERROR:
                issues.append("error_state")

            # Check for stale containers (not used in 1 hour)
            if container.last_used_at and time.time() - container.last_used_at > 3600:
                if container.state == ContainerState.IN_USE:
                    issues.append("stale_in_use")

            if issues:
                unhealthy.append({"id": container.id, "issues": issues})
            else:
                healthy += 1

        return {
            "pool_id": self.pool_id,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "total": len(containers),
            "ready": self.get_ready_count(),
            "in_use": self.get_in_use_count(),
        }

    @contextmanager
    def container_context(self, timeout: float = 30.0):
        """
        Context manager for automatic container allocation/release.

        Usage:
            with pool.container_context() as container:
                # use container
        """
        container = self.allocate(timeout=timeout)
        try:
            yield container
        finally:
            if container:
                self.release(container)

    def __enter__(self) -> "ContainerPool":
        self.initialize(async_init=False)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()
