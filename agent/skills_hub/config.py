"""Skills Hub configuration — all tuning parameters centralized."""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class EscalationCondition:
    """A single escalation trigger condition."""
    condition: str  # e.g. "tool_chain_steps >= 5", "requires_planning"


@dataclass
class DowngradeCondition:
    """A single downgrade trigger condition (all must match — AND logic)."""
    condition: str  # e.g. "tool_chain_steps <= 1", "not requires_planning"


@dataclass
class SkillsHubConfig:
    """Skills Hub configuration.

    Hierarchical config: dict → dataclass, with sane defaults.

    Design principles:
    - Escalation (simple→complex): OR logic — any condition triggers → aggressive.
    - Downgrade (complex→simple): AND logic — all must match → conservative.
    - Tool guard: block expensive tools on simple routes. Complex route = all allowed.
    - On block: escalate to complex by default (never silently skip).
    """

    enabled: bool = False

    # ── Runtime escalation (simple → complex) ──
    # OR logic: any one condition triggers escalation.
    escalation: List[str] = field(default_factory=lambda: [
        "tool_chain_steps >= 5",
        "requires_planning",
        "decision_complexity >= high",
    ])

    # ── Runtime downgrade (complex → simple) ──
    # AND logic: ALL conditions must match for downgrade.
    # Empty list = downgrade disabled.
    downgrade: List[str] = field(default_factory=lambda: [
        "tool_chain_steps <= 1",
        "not requires_planning",
        "decision_complexity != high",
    ])

    # ── Tool guard: tools blocked on simple route ──
    blocked_tools: Dict[str, List[str]] = field(default_factory=lambda: {
        "simple": [
            "delegate_task",
            "execute_code",
            "browser",
            "mcp",
        ],
    })

    # ── Block action ──
    on_block: str = "escalate"   # "escalate" | "warn" | "skip"
    escalate_to: str = "complex"  # target route when escalation triggered

    @classmethod
    def from_dict(cls, d: dict) -> "SkillsHubConfig":
        """Create config from a dict (config.yaml). Missing keys → defaults."""
        if not d:
            return cls()
        return cls(
            enabled=d.get("enabled", False),
            escalation=d.get("runtime_escalation", [
                "tool_chain_steps >= 5",
                "requires_planning",
                "decision_complexity >= high",
            ]),
            downgrade=d.get("runtime_downgrade", [
                "tool_chain_steps <= 1",
                "not requires_planning",
                "decision_complexity != high",
            ]),
            blocked_tools=d.get("blocked_tools", {
                "simple": ["delegate_task", "execute_code", "browser", "mcp"],
            }),
            on_block=d.get("on_block", {}).get("action", "escalate") if isinstance(d.get("on_block"), dict) else "escalate",
            escalate_to=d.get("on_block", {}).get("escalate_to", "complex") if isinstance(d.get("on_block"), dict) else "complex",
        )

    def blocked_for(self, route: str) -> List[str]:
        """Return the list of blocked tools for a given route."""
        return self.blocked_tools.get(route, [])
