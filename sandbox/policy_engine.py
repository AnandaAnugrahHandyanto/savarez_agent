"""
Policy Engine — Rule-based sandbox security policy enforcement.

Provides pre-execution checks for commands and file operations.
Supports custom rules for allowed commands, restricted paths, and
dangerous operation detection.
"""

from __future__ import annotations

import re
import fnmatch
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class PolicyAction(Enum):
    ALLOW = "allow"
    DENY = "deny"
    PROMPT = "prompt"       # require user confirmation
    SANDBOX = "sandbox"     # redirect to sandboxed execution


@dataclass
class PolicyRule:
    """A single policy rule for matching and action."""
    name: str
    pattern: str           # glob pattern to match
    action: PolicyAction
    reason: str = ""       # human-readable explanation
    enabled: bool = True
    priority: int = 0      # higher = evaluated first

    def matches(self, path: str) -> bool:
        """Check if path matches this rule's pattern."""
        return fnmatch.fnmatch(path, self.pattern)


@dataclass
class PolicyResult:
    """Result of a policy evaluation."""
    allowed: bool
    action: PolicyAction
    reason: str
    matched_rule: Optional[PolicyRule] = None


class PolicyEngine:
    """
    Rule-based security policy engine for sandbox operations.

    Default policies:
    - Deny dangerous commands (rm -rf, mkfs, etc.)
    - Restrict access to sensitive paths (/etc, /root, ~/.ssh)
    - Allow safe operations within sandbox workspace
    """

    # Default dangerous command patterns
    DANGEROUS_PATTERNS = [
        ("rm_rf_root", "/rm\\s+-rf\\s+/", PolicyAction.DENY, "Recursive force delete of root"),
        ("dd_zero", "/dd\\s+.*of=/", PolicyAction.DENY, "Disk write via dd"),
        ("mkfs", "/mkfs/", PolicyAction.DENY, "Filesystem format"),
        ("fdisk", "/fdisk/", PolicyAction.DENY, "Partition manipulation"),
        ("mount_bind", "/mount\\s+--bind/", PolicyAction.DENY, "Bind mount"),
        ("chmod_suid", "/chmod\\s+[47]---/", PolicyAction.DENY, "SUID/SGID modification"),
        ("kill_all", "/killall/", PolicyAction.DENY, "Kill all processes"),
        ("reboot", "/reboot/", PolicyAction.DENY, "System reboot"),
        ("shutdown", "/shutdown/", PolicyAction.DENY, "System shutdown"),
    ]

    # Sensitive paths that should be restricted
    SENSITIVE_PATHS = [
        ("/etc/passwd", "/etc/passwd", PolicyAction.DENY, "System password file"),
        ("/etc/shadow", "/etc/shadow", PolicyAction.DENY, "Shadow password file"),
        ("/root", "/root/*", PolicyAction.DENY, "Root home directory"),
        ("/home/*/.ssh", "/home/*/.ssh/*", PolicyAction.DENY, "SSH keys"),
        ("/proc/*/fd", "/proc/*/fd/*", PolicyAction.DENY, "Process file descriptors"),
        ("/dev/sd*", "/dev/sd[a-z][0-9]*", PolicyAction.DENY, "Raw disk devices"),
    ]

    def __init__(self):
        self._rules: List[PolicyRule] = []
        self._enabled = True
        self._custom_checkers: List[Callable[[str, str], Optional[PolicyResult]]] = []
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """Install default security policies."""
        # Add dangerous command patterns
        for name, pattern, action, reason in self.DANGEROUS_PATTERNS:
            self.add_rule(PolicyRule(
                name=name,
                pattern=pattern,
                action=action,
                reason=reason,
                priority=10,
                enabled=True,
            ))

        # Add sensitive path restrictions
        for name, pattern, action, reason in self.SENSITIVE_PATHS:
            self.add_rule(PolicyRule(
                name=name,
                pattern=pattern,
                action=action,
                reason=reason,
                priority=20,
                enabled=True,
            ))

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a policy rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name. Returns True if removed."""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                return True
        return False

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    def check_path(self, path: str) -> PolicyResult:
        """
        Check if a path operation is allowed.
        Returns PolicyResult with action and reason.
        """
        if not self._enabled:
            return PolicyResult(allowed=True, action=PolicyAction.ALLOW, reason="Policy disabled")

        for rule in self._rules:
            if not rule.enabled:
                continue
            if rule.matches(path):
                allowed = rule.action != PolicyAction.DENY
                return PolicyResult(
                    allowed=allowed,
                    action=rule.action,
                    reason=rule.reason,
                    matched_rule=rule,
                )

        return PolicyResult(allowed=True, action=PolicyAction.ALLOW, reason="No matching rule")

    def check_command(self, command: str) -> PolicyResult:
        """
        Check if a shell command is allowed.
        Uses regex matching for command patterns.
        """
        if not self._enabled:
            return PolicyResult(allowed=True, action=PolicyAction.ALLOW, reason="Policy disabled")

        for rule in self._rules:
            if not rule.enabled:
                continue
            if rule.pattern.startswith("/"):
                # Regex pattern (strip leading/trailing slashes)
                try:
                    pattern = rule.pattern.strip("/")
                    if re.search(pattern, command):
                        allowed = rule.action != PolicyAction.DENY
                        return PolicyResult(
                            allowed=allowed,
                            action=rule.action,
                            reason=rule.reason,
                            matched_rule=rule,
                        )
                except re.error:
                    pass

        return PolicyResult(allowed=True, action=PolicyAction.ALLOW, reason="No matching rule")

    def register_checker(self, checker: Callable[[str, str], Optional[PolicyResult]]) -> None:
        """
        Register a custom checker function.

        The checker receives (operation_type, target) and returns
        PolicyResult or None (if checker doesn't handle this case).
        """
        self._custom_checkers.append(checker)

    def evaluate(self, operation: str, target: str) -> PolicyResult:
        """
        Main entry point for policy evaluation.

        Args:
            operation: Type of operation ("read_file", "write_file", "terminal", "delete", etc.)
            target: Target of the operation (path or command)

        Returns:
            PolicyResult with final decision
        """
        # Run custom checkers first
        for checker in self._custom_checkers:
            result = checker(operation, target)
            if result is not None:
                if result.action == PolicyAction.DENY:
                    return result
                elif result.action == PolicyAction.PROMPT:
                    return result

        # Dispatch to appropriate checker
        if operation in ("read_file", "write_file", "delete", "patch", "search_files"):
            return self.check_path(target)
        elif operation in ("terminal", "execute_code"):
            return self.check_command(target)
        else:
            return PolicyResult(
                allowed=True,
                action=PolicyAction.ALLOW,
                reason=f"No policy for operation type: {operation}",
            )

    def get_rules(self) -> List[PolicyRule]:
        """Get all policy rules."""
        return list(self._rules)

    def export_rules(self) -> List[Dict[str, Any]]:
        """Export rules as serializable dict."""
        return [
            {
                "name": r.name,
                "pattern": r.pattern,
                "action": r.action.value,
                "reason": r.reason,
                "enabled": r.enabled,
                "priority": r.priority,
            }
            for r in self._rules
        ]

    @classmethod
    def from_rules(cls, rules_data: List[Dict[str, Any]]) -> "PolicyEngine":
        """Create PolicyEngine from exported rules data."""
        engine = cls()
        engine._rules = []
        for rd in rules_data:
            rule = PolicyRule(
                name=rd["name"],
                pattern=rd["pattern"],
                action=PolicyAction(rd["action"]),
                reason=rd.get("reason", ""),
                enabled=rd.get("enabled", True),
                priority=rd.get("priority", 0),
            )
            engine._rules.append(rule)
        engine._rules.sort(key=lambda r: -r.priority)
        return engine
