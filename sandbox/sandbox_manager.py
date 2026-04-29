"""
Sandbox Manager — Lifecycle management for sandbox instances.

Manages multiple concurrent sandbox instances with independent filesystem
views, resource limits, and security policies. Inspired by CubeSandbox's
lightweight container approach.

Features:
- Multiple concurrent sandboxes with unique IDs
- Independent filesystem views per sandbox
- Integration with ContainerPool for fast allocation
- PolicyEngine for security enforcement
- RollbackManager for deterministic state management
- ResourceTracker for usage monitoring

Sandbox modes:
- Lightweight: Uses process isolation and temporary directories
- Docker: Full container isolation (when available)
"""

from __future__ import annotations

import os
import sys
import time
import uuid
import shutil
import tempfile
import logging
import threading
import subprocess
import concurrent.futures
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Union
from enum import Enum

# Import sandbox components
from sandbox.resource_tracker import ResourceTracker, ResourceQuota, ResourceUsage
from sandbox.policy_engine import PolicyEngine, PolicyAction, PolicyResult
from sandbox.rollback import RollbackManager, RollbackAction
from sandbox.container_pool import ContainerPool, Container, ContainerState

logger = logging.getLogger(__name__)


class SandboxMode(Enum):
    """Sandbox execution modes."""
    LIGHTWEIGHT = "lightweight"  # Process isolation, temp directories
    DOCKER = "docker"           # Full Docker container (when available)
    SINGLE_FILE = "single_file"  # Single-file isolation mode


class SandboxState(Enum):
    """Sandbox instance states."""
    CREATING = "creating"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    ROLLED_BACK = "rolled_back"
    ERROR = "error"
    TERMINATED = "terminated"


@dataclass
class SandboxConfig:
    """Configuration for a sandbox instance."""
    mode: SandboxMode = SandboxMode.LIGHTWEIGHT
    workspace_root: Optional[str] = None
    pool_id: Optional[str] = None
    enable_rollback: bool = True
    auto_snapshot_dangerous: bool = True
    resource_quota: Optional[ResourceQuota] = None
    policy_engine: Optional[PolicyEngine] = None
    timeout: float = 300.0  # seconds
    environment_vars: Dict[str, str] = field(default_factory=dict)
    allowed_paths: List[str] = field(default_factory=list)  # whitelisted paths
    denied_paths: List[str] = field(default_factory=list)   # blacklisted paths

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "workspace_root": self.workspace_root,
            "pool_id": self.pool_id,
            "enable_rollback": self.enable_rollback,
            "auto_snapshot_dangerous": self.auto_snapshot_dangerous,
            "timeout": self.timeout,
            "environment_vars": self.environment_vars,
            "allowed_paths": self.allowed_paths,
            "denied_paths": self.denied_paths,
        }


@dataclass
class ExecutionResult:
    """Result of sandbox execution."""
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    duration: float = 0.0
    sandbox_id: str = ""
    resources: Optional[Dict[str, Any]] = None
    rollback_performed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Sandbox:
    """
    A single sandbox instance with isolated workspace and resources.

    Attributes:
        id: Unique sandbox identifier
        config: Sandbox configuration
        state: Current sandbox state
        workspace_path: Isolated filesystem workspace
        container: Optional pooled container reference
    """
    id: str
    config: SandboxConfig
    state: SandboxState = SandboxState.CREATING
    workspace_path: str = ""
    created_at: float = field(default_factory=time.time)
    last_used_at: Optional[float] = None
    container: Optional[Container] = None

    # Components
    resource_tracker: Optional[ResourceTracker] = None
    policy_engine: Optional[PolicyEngine] = None
    rollback_manager: Optional[RollbackManager] = None

    # Execution context
    _execution_count: int = 0
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "config": self.config.to_dict(),
            "state": self.state.value,
            "workspace_path": self.workspace_path,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "execution_count": self._execution_count,
            "container_id": self.container.id if self.container else None,
        }

    def is_active(self) -> bool:
        """Check if sandbox is in an active state."""
        return self.state in (SandboxState.READY, SandboxState.RUNNING)

    def execute(self, command: str, timeout: Optional[float] = None) -> ExecutionResult:
        """Execute a command within this sandbox."""
        raise NotImplementedError("Use SandboxManager.execute() instead")

    def rollback(self, snapshot_id: Optional[str] = None) -> bool:
        """Rollback sandbox to a previous state."""
        if not self.rollback_manager:
            logger.warning(f"Sandbox {self.id} has no rollback manager")
            return False
        return self.rollback_manager.rollback(snapshot_id)


class SandboxManager:
    """
    Central manager for sandbox instances.

    Features:
    - Create and manage multiple concurrent sandboxes
    - Container pool integration for fast allocation
    - Global policy engine and resource quotas
    - Sandbox state machine management
    - Execution with policy enforcement and rollback

    Usage:
        manager = SandboxManager()
        sandbox = manager.create()
        result = sandbox.execute("echo hello")
        manager.destroy(sandbox.id)
    """

    # Global pool for lightweight containers
    _global_pool: Optional[ContainerPool] = None
    _pool_lock = threading.Lock()

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        pool_size: int = 5,
        default_timeout: float = 300.0,
        default_quota: Optional[ResourceQuota] = None,
        default_policy: Optional[PolicyEngine] = None,
    ):
        """
        Initialize SandboxManager.

        Args:
            workspace_root: Root directory for sandbox workspaces
            pool_size: Size of pre-warmed container pool
            default_timeout: Default execution timeout
            default_quota: Default resource quotas
            default_policy: Default policy engine
        """
        self._workspace_root = workspace_root or tempfile.mkdtemp(prefix="sandbox_root_")
        self._default_timeout = default_timeout
        self._default_quota = default_quota or ResourceQuota()
        self._default_policy = default_policy or PolicyEngine()

        self._sandboxes: Dict[str, Sandbox] = {}
        self._lock = threading.RLock()

        # Container pool
        self._pool = self._get_or_create_pool(pool_size)

        # Global statistics
        self._stats = {
            "total_created": 0,
            "total_destroyed": 0,
            "total_executions": 0,
            "total_rollbacks": 0,
            "total_policy_denials": 0,
        }

    @classmethod
    def _get_or_create_pool(cls, size: int) -> ContainerPool:
        """Get or create the global container pool."""
        with cls._pool_lock:
            if cls._global_pool is None:
                cls._global_pool = ContainerPool(
                    pool_id="global_sandbox_pool",
                    size=size,
                )
                cls._global_pool.initialize(async_init=True)
            return cls._global_pool

    def get_global_pool(self) -> ContainerPool:
        """Get the global container pool."""
        return self._pool

    def create(self, config: Optional[SandboxConfig] = None) -> Sandbox:
        """
        Create a new sandbox instance.

        Args:
            config: Optional sandbox configuration

        Returns:
            Sandbox instance
        """
        config = config or SandboxConfig()
        sandbox_id = f"sbox_{uuid.uuid4().hex[:12]}"

        # Determine workspace path
        if config.workspace_root:
            workspace = os.path.join(config.workspace_root, sandbox_id)
        elif config.pool_id:
            # Try to get container from pool
            container = self._pool.allocate(timeout=5.0)
            if container:
                workspace = container.workspace_path
            else:
                workspace = os.path.join(self._workspace_root, sandbox_id)
                os.makedirs(workspace, exist_ok=True)
        else:
            workspace = os.path.join(self._workspace_root, sandbox_id)
            os.makedirs(workspace, exist_ok=True)

        # Create sandbox
        sandbox = Sandbox(
            id=sandbox_id,
            config=config,
            state=SandboxState.READY,
            workspace_path=workspace,
            container=None,
        )

        # Initialize components
        sandbox.resource_tracker = ResourceTracker(
            sandbox_id=sandbox_id,
            quota=config.resource_quota or self._default_quota,
        )

        sandbox.policy_engine = config.policy_engine or self._default_policy

        if config.enable_rollback:
            sandbox.rollback_manager = RollbackManager(
                sandbox_id=sandbox_id,
                workspace_root=workspace,
            )
            # Create initial snapshot
            sandbox.rollback_manager.create_snapshot(description="initial")

        with self._lock:
            self._sandboxes[sandbox_id] = sandbox
            self._stats["total_created"] += 1

        logger.info(f"Created sandbox {sandbox_id} with workspace {workspace}")
        return sandbox

    def destroy(self, sandbox_id: str) -> bool:
        """
        Destroy a sandbox instance.

        Args:
            sandbox_id: ID of sandbox to destroy

        Returns:
            True if destroyed
        """
        with self._lock:
            sandbox = self._sandboxes.get(sandbox_id)
            if not sandbox:
                return False

            # Release container back to pool
            if sandbox.container:
                self._pool.release(sandbox.container)
                sandbox.container = None

            # Cleanup rollback manager
            if sandbox.rollback_manager:
                sandbox.rollback_manager.cleanup()

            # Remove workspace
            if os.path.exists(sandbox.workspace_path):
                shutil.rmtree(sandbox.workspace_path, ignore_errors=True)

            sandbox.state = SandboxState.TERMINATED
            del self._sandboxes[sandbox_id]
            self._stats["total_destroyed"] += 1

            logger.info(f"Destroyed sandbox {sandbox_id}")
            return True

    def get(self, sandbox_id: str) -> Optional[Sandbox]:
        """Get sandbox by ID."""
        return self._sandboxes.get(sandbox_id)

    def list(self) -> List[Sandbox]:
        """List all sandboxes."""
        return list(self._sandboxes.values())

    def execute(
        self,
        sandbox_id: str,
        command: str,
        timeout: Optional[float] = None,
        check_policy: bool = True,
    ) -> ExecutionResult:
        """
        Execute a command within a sandbox.

        Args:
            sandbox_id: Target sandbox ID
            command: Command to execute
            timeout: Execution timeout
            check_policy: Whether to check policy before execution

        Returns:
            ExecutionResult
        """
        start_time = time.time()
        sandbox = self._sandboxes.get(sandbox_id)

        if not sandbox:
            return ExecutionResult(
                success=False,
                error=f"Sandbox {sandbox_id} not found",
                sandbox_id=sandbox_id,
            )

        if not sandbox.is_active():
            return ExecutionResult(
                success=False,
                error=f"Sandbox {sandbox_id} is not active (state: {sandbox.state})",
                sandbox_id=sandbox_id,
            )

        # Policy check
        if check_policy and sandbox.policy_engine:
            result = sandbox.policy_engine.check_command(command)
            if not result.allowed:
                self._stats["total_policy_denials"] += 1
                return ExecutionResult(
                    success=False,
                    error=f"Policy denied: {result.reason}",
                    sandbox_id=sandbox_id,
                    duration=time.time() - start_time,
                    metadata={"matched_rule": result.matched_rule.name if result.matched_rule else None},
                )

        # Auto snapshot for dangerous operations
        rollback_performed = False
        if sandbox.config.auto_snapshot_dangerous and sandbox.rollback_manager:
            if sandbox.rollback_manager.is_dangerous(command):
                sandbox.rollback_manager.create_snapshot(
                    description=f"pre-exec: {command[:50]}",
                    auto=True,
                )

        # Resource check
        if sandbox.resource_tracker:
            allowed, reason = sandbox.resource_tracker.check_quota()
            if not allowed:
                return ExecutionResult(
                    success=False,
                    error=f"Resource quota exceeded: {reason}",
                    sandbox_id=sandbox_id,
                    duration=time.time() - start_time,
                )

        # Execute command
        sandbox.state = SandboxState.RUNNING
        timeout = timeout or sandbox.config.timeout or self._default_timeout

        try:
            # Build environment
            env = os.environ.copy()
            env.update(sandbox.config.environment_vars)
            env["SANDBOX_ID"] = sandbox_id
            env["SANDBOX_WORKSPACE"] = sandbox.workspace_path

            # Execute
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=sandbox.workspace_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                return ExecutionResult(
                    success=False,
                    error=f"Execution timed out after {timeout}s",
                    exit_code=-1,
                    sandbox_id=sandbox_id,
                    duration=time.time() - start_time,
                    rollback_performed=rollback_performed,
                )

            duration = time.time() - start_time

            # Update sandbox
            with sandbox._lock:
                sandbox._execution_count += 1
                sandbox.last_used_at = time.time()
                sandbox.state = SandboxState.READY

            # Update resource tracker
            if sandbox.resource_tracker:
                sandbox.resource_tracker.record_cpu_time(duration)

            self._stats["total_executions"] += 1

            return ExecutionResult(
                success=exit_code == 0,
                output=stdout,
                error=stderr,
                exit_code=exit_code,
                duration=duration,
                sandbox_id=sandbox_id,
                resources=sandbox.resource_tracker.summary() if sandbox.resource_tracker else None,
                rollback_performed=rollback_performed,
            )

        except Exception as e:
            logger.error(f"Execution error in sandbox {sandbox_id}: {e}")
            sandbox.state = SandboxState.ERROR
            return ExecutionResult(
                success=False,
                error=str(e),
                sandbox_id=sandbox_id,
                duration=time.time() - start_time,
            )

    def rollback(self, sandbox_id: str, snapshot_id: Optional[str] = None) -> bool:
        """
        Rollback a sandbox to a previous state.

        Args:
            sandbox_id: Target sandbox ID
            snapshot_id: Optional specific snapshot ID

        Returns:
            True if successful
        """
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox or not sandbox.rollback_manager:
            return False

        result = sandbox.rollback_manager.rollback(snapshot_id)
        if result:
            sandbox.state = SandboxState.ROLLED_BACK
            self._stats["total_rollbacks"] += 1

            # Schedule state back to READY
            def reset_state():
                time.sleep(0.1)
                sandbox.state = SandboxState.READY

            threading.Thread(target=reset_state, daemon=True).start()

        return result

    def snapshot(self, sandbox_id: str, description: str = "") -> Optional[str]:
        """
        Create a snapshot of sandbox state.

        Args:
            sandbox_id: Target sandbox ID
            description: Snapshot description

        Returns:
            Snapshot ID if successful
        """
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox or not sandbox.rollback_manager:
            return None
        return sandbox.rollback_manager.create_snapshot(description=description)

    def get_stats(self) -> Dict[str, Any]:
        """Get global statistics."""
        return {
            **self._stats,
            "active_sandboxes": sum(1 for s in self._sandboxes.values() if s.is_active()),
            "total_sandboxes": len(self._sandboxes),
            "pool_stats": self._pool.get_stats() if self._pool else None,
        }

    def cleanup_all(self) -> int:
        """
        Clean up all sandboxes.

        Returns:
            Number of sandboxes destroyed
        """
        with self._lock:
            count = len(self._sandboxes)
            for sandbox_id in list(self._sandboxes.keys()):
                self.destroy(sandbox_id)
            return count

    def __enter__(self) -> "SandboxManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup_all()
        if self._pool:
            self._pool.cleanup()
