"""Approval configuration."""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class HardRule:
    """A hard rule matched against action name and args."""
    action: str              # tool name to match
    args_pattern: str = ""   # regex pattern to match in serialized args


@dataclass
class ApprovalConfig:
    """Safety approval gate configuration.

    Three steps:
    1. Hard rules (zero LLM) — block/always_ask lists
    2. LLM risk assessment — for nuanced cases
    3. Decision — reject high/medium, allow low
    """

    enabled: bool = False

    # ── Step 1: Hard rules ──
    hard_rules: dict = field(default_factory=lambda: {
        "block": [
            {"action": "terminal", "args_pattern": r"rm\s+-rf|DROP\s+TABLE|drop_database|format\s+disk"},
        ],
        "always_ask": [
            {"action": "send_message", "args_pattern": r"post_public|bulk|broadcast"},
            {"action": "delegate_task", "args_pattern": r"删库|rm\s+-rf|drop\s+table"},
        ],
    })

    # ── Step 2: LLM risk assessment ──
    risk_model: dict = field(default_factory=lambda: {
        "default": "deepseek-v4-flash",       # most assessments use flash
        "high_risk_actions": [                # known nuanced tools → use pro
            "terminal",                    # (delegate_task handled by whitelist)
        ],
        "force_high_if_confidence": 0.7,      # model unsure → reject
        "timeout": 15,                         # seconds (raised from 5 — DeepSeek latency)
    })

    # ── Step 3: Decisions ──
    decisions: dict = field(default_factory=lambda: {
        "high": "reject",
        "medium": "reject",
        "low": "allow",
    })

    audit_log: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> "ApprovalConfig":
        """Create config from a dict (config.yaml). Missing keys → defaults."""
        if not d:
            return cls()
        kwargs = {"enabled": d.get("enabled", False)}
        if d.get("hard_rules"):
            kwargs["hard_rules"] = d["hard_rules"]
        if d.get("risk_model"):
            kwargs["risk_model"] = d["risk_model"]
        if d.get("decisions"):
            kwargs["decisions"] = d["decisions"]
        if "audit_log" in d:
            kwargs["audit_log"] = d["audit_log"]
        return cls(**kwargs)

    def is_high_risk_action(self, action: str) -> bool:
        """Check if this action needs pro model for assessment."""
        return action in self.risk_model.get("high_risk_actions", [])

    def decision_for(self, risk_level: str) -> str:
        """Map risk_level → allow/reject."""
        return self.decisions.get(risk_level, "reject")
