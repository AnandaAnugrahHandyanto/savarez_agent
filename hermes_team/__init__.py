"""Hermes-native team orchestration package.

Purpose:
- Keep team task/approval/registry state inside HERMES_HOME/state/team/.
- Expose Hermes-native task, approval, and registry stores.
- Restrict historical compatibility helpers to explicit migration/bootstrap flows.
"""

from .paths import get_team_state_dir
from .json_store import JsonStateStore
from .task_store import TaskStore
from .approval_store import ApprovalStore
from .registry_store import RegistryStore
from .approval_gate import ApprovalDecision, ApprovalGate
from .approval_manager import TeamApprovalManager
from .approval_audit import ApprovalAuditReport, ApprovalAuditReporter
from .metrics import TeamMetrics, TeamMetricsStore
from .metrics_reporter import TeamMetricsReport, TeamMetricsReporter
from .replanner import ReplanDecision, ReplanStore, TeamReplanner
from .sandbox import TeamSandboxAuditStore, TeamSandboxPolicy, TeamSandboxPolicyEngine
from .watcher import TeamWatcher, TeamWatchSnapshot, TeamWatchStore
from .roles import TeamRole, RoleRegistry
from .task_graph import TeamGraphNode, TeamGraphResult, TeamGraphRunner, TeamTaskGraph
from .messages import TeamEvent, TeamEventStore
from .dispatcher import DispatchRequest, DispatchResult, TeamDispatcher
from .orchestrator import TeamRunSpec, TeamRunResult, TeamOrchestrator

__all__ = [
    "get_team_state_dir",
    "JsonStateStore",
    "TaskStore",
    "ApprovalStore",
    "RegistryStore",
    "ApprovalDecision",
    "ApprovalGate",
    "TeamApprovalManager",
    "ApprovalAuditReport",
    "ApprovalAuditReporter",
    "TeamMetrics",
    "TeamMetricsStore",
    "TeamMetricsReport",
    "TeamMetricsReporter",
    "ReplanDecision",
    "ReplanStore",
    "TeamReplanner",
    "TeamSandboxAuditStore",
    "TeamSandboxPolicy",
    "TeamSandboxPolicyEngine",
    "TeamWatcher",
    "TeamWatchSnapshot",
    "TeamWatchStore",
    "TeamRole",
    "RoleRegistry",
    "TeamGraphNode",
    "TeamGraphResult",
    "TeamGraphRunner",
    "TeamTaskGraph",
    "TeamEvent",
    "TeamEventStore",
    "DispatchRequest",
    "DispatchResult",
    "TeamDispatcher",
    "TeamRunSpec",
    "TeamRunResult",
    "TeamOrchestrator",
]
