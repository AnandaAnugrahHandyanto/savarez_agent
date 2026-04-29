"""
Hermes Agent — Sandbox Isolation Module

Lightweight sandbox isolation inspired by TencentCloud/CubeSandbox.
Provides instant, concurrent, secure, lightweight AI Agent sandboxing
with deterministic rollback capabilities.

Components:
    - SandboxManager    : Lifecycle management for multiple sandbox instances
    - ContainerPool     : Pre-warmed container pool for fast allocation
    - Rollback          : Deterministic state snapshots and rollback
    - PolicyEngine      : Rule-based security policy enforcement
    - ResourceTracker   : CPU, memory, disk usage tracking and quotas

Usage:
    from sandbox import SandboxManager
    manager = SandboxManager()
    sandbox = manager.create()
    result = sandbox.execute("echo hello")
    sandbox.rollback()  # revert to clean state
"""

from sandbox.sandbox_manager import SandboxManager
from sandbox.container_pool import ContainerPool
from sandbox.rollback import RollbackManager, Snapshot
from sandbox.policy_engine import PolicyEngine
from sandbox.resource_tracker import ResourceTracker

__all__ = [
    "SandboxManager",
    "ContainerPool",
    "RollbackManager",
    "Snapshot",
    "PolicyEngine",
    "ResourceTracker",
]
