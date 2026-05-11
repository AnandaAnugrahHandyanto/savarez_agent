"""Approval — safety gate before tool execution.

Three steps:
1. Hard rules: BLOCK list (regex) + ALWAYS_ASK list — zero LLM cost.
2. LLM risk assessment: for nuanced tools, ask a model to judge risk.
3. Decision: reject high/medium, allow low.

Ordered BEFORE Skills Hub in the execution pipeline — safety before cost.
"""

from .config import ApprovalConfig
from .guard import ApprovalGuard, ApprovalDecision

__all__ = [
    "ApprovalConfig",
    "ApprovalGuard",
    "ApprovalDecision",
]
