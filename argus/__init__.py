"""Argus - Agent Resource Guardian & Unified Supervisor.

Entropy detection and session monitoring for Hermes agents.
"""

# Core
from .argus import Argus

# Detection functions
from .entropy import (
    detect_repeat_tool_calls,
    detect_repeat_commands,
    detect_stuck_loops,
    detect_no_file_changes,
    detect_error_cascade,
    detect_budget_pressure,
)

# Actions
from .actions import (
    kill_session,
    restart_session,
    inject_prompt,
    strip_session_prefix,
)

# Notifications
from .notifications import (
    send_notification,
    send_telegram,
    send_discord,
    send_slack,
    send_matrix,
    send_webhook,
    send_via_gateway,
)

# Metrics
from .metrics import MetricsCollector, write_metrics_file

# ML Data (optional feature)
from .ml_data import (
    MLDataExporter,
    HolographicMemoryBridge,
    export_entropy_event,
)

# Cost Monitoring
from .cost_monitor import CostMonitor, check_costs, format_cost_alert

# Circuit Breaker
from .circuit_breaker import CircuitBreaker, check_circuits, format_circuit_event

__all__ = [
    # Core
    "Argus",
    # Detection
    "detect_repeat_tool_calls",
    "detect_repeat_commands",
    "detect_stuck_loops",
    "detect_no_file_changes",
    "detect_error_cascade",
    "detect_budget_pressure",
    # Actions
    "kill_session",
    "restart_session",
    "inject_prompt",
    "strip_session_prefix",
    # Notifications
    "send_notification",
    "send_telegram",
    "send_discord",
    "send_slack",
    "send_matrix",
    "send_webhook",
    "send_via_gateway",
    # Metrics
    "MetricsCollector",
    "write_metrics_file",
    # ML Data (optional)
    "MLDataExporter",
    "HolographicMemoryBridge",
    "export_entropy_event",
    # Cost Monitoring
    "CostMonitor",
    "check_costs",
    "format_cost_alert",
    # Circuit Breaker
    "CircuitBreaker",
    "check_circuits",
    "format_circuit_event",
]
