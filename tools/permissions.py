#!/usr/bin/env python3
"""
Hermes Agent Permission System - Claude Code-level security capabilities.

Provides:
- PermissionMode: READ / EDIT / ASK / AUTO four-tier access control
- PathRule: glob pattern-based allow/deny rules
- DangerousPattern: regex collection for dangerous commands
- resolve_permission(): determines permission level for a tool call
- Session-level permission memory
- Integration with pre_tool_call hook
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Permission Mode Enum
# =============================================================================

class PermissionMode(Enum):
    """Four-tier permission model."""
    READ = "read"      # Read-only access, no modifications
    EDIT = "edit"      # Can read and write existing files
    ASK = "ask"        # Must prompt user for confirmation
    AUTO = "auto"     # Full automation, auto-allow safe, auto-deny dangerous
    DENY = "deny"     # Explicitly denied


# =============================================================================
# Dangerous Pattern Definitions
# =============================================================================

# Patterns matched against the full command string
_DANGEROUS_PATTERNS: List[Tuple[str, re.Pattern, str]] = [
    # File destruction
    ("rm_rf", re.compile(r'\brm\s+-[rf]+\s+'), "Recursive delete with rm"),
    ("rm_rf_force", re.compile(r'\brm\s+-[rf]+f+\s+'), "Recursive force delete"),
    ("delete_boot", re.compile(r'\brm\s+-[rf]+\s+/dev/\S*'), "Delete device files"),
    ("shred", re.compile(r'\bshred\s+'), "Secure file deletion"),
    ("truncate_zero", re.compile(r'\btruncate\s+--size=0\b'), "Truncate to zero size"),

    # Git dangerous operations
    ("git_reset_hard", re.compile(r'\bgit\s+reset\s+--hard\b'), "Git hard reset"),
    ("git_push_force", re.compile(r'\bgit\s+push\s+--force\b'), "Force push to remote"),
    ("git_push_force_with lease", re.compile(r'\bgit\s+push\s+--force-with-lease\b'), "Force push with lease"),
    ("git_push_delete", re.compile(r'\bgit\s+push\s+--delete\b'), "Delete remote branch"),
    ("git_branch_D", re.compile(r'\bgit\s+branch\s+-D\b'), "Force delete git branch"),

    # Disk operations
    ("dd", re.compile(r'\bdd\s+'), "Low-level disk copy/format"),
    ("fdisk", re.compile(r'\bfdisk\s+'), "Partition table manipulation"),
    ("mkfs", re.compile(r'\bmkfs\b'), "Filesystem creation"),
    ("mount_bind", re.compile(r'\bmount\s+--bind\b'), "Mount bind operation"),

    # In-place editing with sed/awk that can corrupt files
    ("sed_i", re.compile(r'\bsed\s+-i\b'), "Sed in-place editing (can corrupt)"),
    ("awk_i", re.compile(r'\bawk\s+-[Fi]\b.*-i\b'), "Awk in-place editing"),

    # Fork bombs and DoS
    ("fork_bomb", re.compile(r':\(\)\{\s*:\|:\s*&\s*\};:'), "Fork bomb"),
    ("fork_bomb_alt", re.compile(r'\b:\|:\|:'), "Fork bomb variant"),

    # Chmod dangerous
    ("chmod_777", re.compile(r'\bchmod\s+777\b'), "World-writable permissions"),
    ("chmod_000", re.compile(r'\bchmod\s+000\b'), "Remove all permissions"),

    # Download and execute (potential malware)
    ("curl_sh", re.compile(r'\bcurl\s+.*\|\s*sh\b'), "Download and execute script"),
    ("wget_sh", re.compile(r'\bwget\s+.*\|\s*(?:sh|bash)\b'), "Download and execute script"),

    # Systemctl
    ("systemctl_stop", re.compile(r'\bsystemctl\s+stop\b'), "Stop system service"),
    ("systemctl_disable", re.compile(r'\bsystemctl\s+disable\b'), "Disable system service"),

    # Service manipulation
    ("service_stop", re.compile(r'\bservice\s+\S+\s+stop\b'), "Stop service"),
    ("launchctl_unload", re.compile(r'\blaunchctl\s+unload\b'), "Unload launchd service (macOS)"),

    # Firewall
    ("iptables_flush", re.compile(r'\biptables\s+-F\b'), "Flush iptables rules"),
    ("ufw_disable", re.compile(r'\bufw\s+disable\b'), "Disable UFW firewall"),

    # Process termination
    ("killall", re.compile(r'\bkillall\s+-9?\b'), "Force kill all processes"),
    ("pkill", re.compile(r'\bpkill\s+'), "Kill processes by name"),

    # SSH key manipulation
    ("ssh_keygen_overwrite", re.compile(r'\bssh-keygen\s+.*-f\s+~\/.ssh\/'), "Overwrite SSH keys"),
]


# Tools classified by danger level
_TOOL_DANGER_LEVEL: Dict[str, str] = {
    "Bash": "high",
    "Write": "medium",
    "Edit": "medium",
    "Read": "low",
    "terminal_tool": "high",
    "file_tools": "medium",
}


# =============================================================================
# Path Rule Matching
# =============================================================================

def _expand_glob_pattern(pattern: str) -> str:
    """Expand ~ and resolve relative paths in glob patterns."""
    if pattern.startswith("~/"):
        return os.path.expanduser(pattern)
    return pattern


def _match_glob(path: str, pattern: str) -> bool:
    """Match a path against a glob pattern, supporting ** for directories."""
    pattern = _expand_glob_pattern(pattern)
    # Handle ** recursively - ** at end of pattern matches any number of path components
    if "**" in pattern:
        if pattern.endswith("/**"):
            # /home/user/protected/** matches /home/user/protected/anything/anywhere
            prefix = pattern[:-3]  # Remove /**
            return path.startswith(prefix + "/") or path == prefix
        elif "**" in pattern:
            # More complex ** pattern
            parts = pattern.split("**")
            if len(parts) == 2:
                prefix, suffix = parts
                if prefix and path.startswith(prefix):
                    if suffix:
                        return suffix in path[len(prefix):]
                    return True
        return False  # Fallback: ** patterns that aren't prefix-based are complex
    return fnmatch.fnmatch(path, pattern)


def _check_path_rules(
    path: str,
    deny_rules: List[str],
    allow_rules: List[str]
) -> Tuple[bool, bool]:
    """Check path against deny/allow rules. Returns (is_denied, is_allowed)."""
    # Expand ~ in the input path
    expanded_path = os.path.expanduser(path)

    # Normalize to absolute for consistent matching
    try:
        abs_path = str(Path(expanded_path).resolve())
    except (OSError, RuntimeError):
        abs_path = expanded_path

    # Also keep the original for fallback matching
    try:
        orig_abs_path = str(Path(path).resolve()) if path != expanded_path else abs_path
    except (OSError, RuntimeError):
        orig_abs_path = abs_path

    # Check deny rules first
    for rule in deny_rules:
        if _match_glob(abs_path, rule) or _match_glob(expanded_path, rule) or _match_glob(orig_abs_path, rule):
            return True, False

    # Check allow rules
    for rule in allow_rules:
        if _match_glob(abs_path, rule) or _match_glob(expanded_path, rule) or _match_glob(orig_abs_path, rule):
            return False, True

    return False, False


# =============================================================================
# Command Sanitization
# =============================================================================

# Patterns for sensitive data to mask in command display
_SANITIZE_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # API keys - sk- prefix (OpenAI, Anthropic, etc.)
    ("sk_key", re.compile(r'sk-[A-Za-z0-9_-]{10,}')),
    # Stripe keys sk_live_ and sk_test_
    ("sk_live_key", re.compile(r'sk_live_[A-Za-z0-9]{10,}')),
    ("sk_test_key", re.compile(r'sk_test_[A-Za-z0-9]{10,}')),
    # GitHub tokens
    ("ghp_token", re.compile(r'ghp_[A-Za-z0-9]{10,}')),
    ("github_pat", re.compile(r'github_pat_[A-Za-z0-9_]{10,}')),
    # Slack tokens
    ("slack_token", re.compile(r'xox[baprs]-[A-Za-z0-9-]{10,}')),
    # AWS keys
    ("aws_key", re.compile(r'AKIA[A-Z0-9]{16}')),
    # SendGrid
    ("sendgrid_key", re.compile(r'SG\.[A-Za-z0-9_-]{10,}')),
    # HuggingFace
    ("hf_token", re.compile(r'hf_[A-Za-z0-9]{10,}')),
    # Environment variables with secrets - check after specific patterns
    ("env_secret", re.compile(r'[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD|KEY)[A-Z0-9_]*=\S+')),
    # URLs with credentials
    ("url_creds", re.compile(r'://[^:]+:[^@]+@')),
    # Bearer tokens
    ("bearer_token", re.compile(r'Bearer\s+[A-Za-z0-9_-]{10,}')),
]


def sanitize_command(command: str) -> str:
    """Remove sensitive information from command for safe display."""
    result = command
    for name, pattern in _SANITIZE_PATTERNS:
        result = pattern.sub(lambda m: f"[{name.upper()}_REDACTED]", result)
    return result


# =============================================================================
# Session Permission Memory
# =============================================================================

@dataclass
class PermissionDecision:
    """A remembered permission decision for a session."""
    tool_name: str
    target: str  # file path or command pattern
    decision: str  # "allow_once", "allow_always", "deny"
    is_permanent: bool = False


class SessionPermissionMemory:
    """Thread-safe session-level permission memory."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._decisions: List[PermissionDecision] = []
        self._always_allow_paths: List[str] = []
        self._always_allow_commands: List[str] = []
        self._always_deny_paths: List[str] = []
        self._always_deny_commands: List[str] = []

    def remember(
        self,
        tool_name: str,
        target: str,
        decision: str,
        is_permanent: bool = False
    ) -> None:
        """Remember a permission decision."""
        with self._lock:
            # Remove any previous decision for same tool+target
            self._decisions = [
                d for d in self._decisions
                if not (d.tool_name == tool_name and d.target == target)
            ]
            self._decisions.append(PermissionDecision(
                tool_name=tool_name,
                target=target,
                decision=decision,
                is_permanent=is_permanent
            ))

            if is_permanent:
                if decision == "allow_always":
                    if tool_name in ("Write", "Edit"):
                        self._always_allow_paths.append(target)
                    elif tool_name == "Bash":
                        self._always_allow_commands.append(target)
                elif decision == "deny":
                    if tool_name in ("Write", "Edit"):
                        self._always_deny_paths.append(target)
                    elif tool_name == "Bash":
                        self._always_deny_commands.append(target)

    def lookup(self, tool_name: str, target: str) -> Optional[str]:
        """Look up a remembered decision. Returns decision string or None."""
        with self._lock:
            for decision in reversed(self._decisions):
                if decision.tool_name == tool_name and decision.target == target:
                    return decision.decision
            return None

    def is_path_always_allowed(self, path: str) -> bool:
        """Check if path is always allowed."""
        with self._lock:
            for rule in self._always_allow_paths:
                if _match_glob(path, rule):
                    return True
            return False

    def is_path_always_denied(self, path: str) -> bool:
        """Check if path is always denied (permanently marked as deny)."""
        with self._lock:
            for rule in self._always_deny_paths:
                if _match_glob(path, rule):
                    return True
            return False

    def is_command_always_allowed(self, command: str) -> bool:
        """Check if command is always allowed."""
        with self._lock:
            for pattern in self._always_allow_commands:
                if pattern in command or _match_glob(command, pattern):
                    return True
            return False

    def is_command_always_denied(self, command: str) -> bool:
        """Check if command is always denied."""
        with self._lock:
            for pattern in self._always_deny_commands:
                if pattern in command or _match_glob(command, pattern):
                    return True
            return False

    def clear(self) -> None:
        """Clear all remembered decisions."""
        with self._lock:
            self._decisions.clear()
            self._always_allow_paths.clear()
            self._always_allow_commands.clear()
            self._always_deny_paths.clear()
            self._always_deny_commands.clear()


# =============================================================================
# Permission Configuration
# =============================================================================

def _get_default_permissions_config() -> Dict:
    """Get default permissions configuration."""
    home = os.path.expanduser("~")
    return {
        "mode": "ask",
        "deny": [f"{home}/protected/**"],
        "allow": [f"{home}/.hermes/**"],
    }


def load_permissions_config() -> Dict:
    """Load permissions config from config.yaml."""
    try:
        from hermes_cli.config import load_config
        config = load_config()
        perms = config.get("permissions", {})
        if not perms:
            return _get_default_permissions_config()
        # Validate required fields
        if "mode" not in perms:
            perms["mode"] = "ask"
        if "deny" not in perms:
            perms["deny"] = _get_default_permissions_config()["deny"]
        if "allow" not in perms:
            perms["allow"] = _get_default_permissions_config()["allow"]
        return perms
    except Exception as exc:
        logger.warning("Failed to load permissions config: %s, using defaults", exc)
        return _get_default_permissions_config()


# =============================================================================
# Global Permission Resolver
# =============================================================================

class PermissionResolver:
    """Central permission resolution engine."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._session_memory: Dict[str, SessionPermissionMemory] = {}
        self._config: Optional[Dict] = None

    def _get_config(self) -> Dict:
        """Get cached or fresh config."""
        with self._lock:
            if self._config is None:
                self._config = load_permissions_config()
            return self._config

    def invalidate_config(self) -> None:
        """Invalidate cached config (for testing or config reload)."""
        with self._lock:
            self._config = None

    def get_session_memory(self, session_id: str) -> SessionPermissionMemory:
        """Get or create session memory for a session."""
        with self._lock:
            if session_id not in self._session_memory:
                self._session_memory[session_id] = SessionPermissionMemory()
            return self._session_memory[session_id]

    def clear_session(self, session_id: str) -> None:
        """Clear session memory."""
        with self._lock:
            if session_id in self._session_memory:
                del self._session_memory[session_id]

    def _check_dangerous_command(self, command: str) -> Tuple[bool, List[str]]:
        """Check if command matches dangerous patterns. Returns (is_dangerous, descriptions)."""
        dangerous = []
        for name, pattern, description in _DANGEROUS_PATTERNS:
            if pattern.search(command):
                dangerous.append(description)
        return len(dangerous) > 0, dangerous

    def _classify_tool_access(self, tool_name: str) -> str:
        """Classify tool access level."""
        normalized = tool_name.lower()
        if normalized in ("read", "read_file", "glob", "grep", "search"):
            return "read"
        elif normalized in ("write", "edit", "patch", "terminal_tool", "bash", "execute"):
            return "write"
        return "unknown"

    def resolve_permission(
        self,
        tool_name: str,
        file_path: Optional[str] = None,
        command: Optional[str] = None,
        session_id: str = "default",
    ) -> Tuple[PermissionMode, str]:
        """
        Determine permission mode for a tool call.

        Returns (mode, reason) tuple.
        """
        config = self._get_config()
        mode_str = config.get("mode", "ask")
        deny_rules = config.get("deny", [])
        allow_rules = config.get("allow", [])

        # Parse configured mode
        try:
            base_mode = PermissionMode(mode_str)
        except ValueError:
            base_mode = PermissionMode.ASK

        session_mem = self.get_session_memory(session_id)

        # Check session memory first
        if file_path:
            # Check path memory
            if session_mem.is_path_always_allowed(file_path):
                return PermissionMode.AUTO, "always allowed path"
            if session_mem.is_path_always_denied(file_path):
                return PermissionMode.READ, "always denied path"

            # Check specific decision
            decision = session_mem.lookup(tool_name, file_path)
            if decision:
                if decision == "allow_always":
                    return PermissionMode.AUTO, "always allowed"
                elif decision == "allow_once":
                    return PermissionMode.EDIT, "allowed once"
                elif decision == "deny":
                    return PermissionMode.READ, "denied"

            # Check path rules
            is_denied, is_allowed = _check_path_rules(file_path, deny_rules, allow_rules)
            if is_denied and base_mode in (PermissionMode.EDIT, PermissionMode.ASK):
                return PermissionMode.ASK, "path in deny list"

        if command:
            # Check command memory
            if session_mem.is_command_always_allowed(command):
                return PermissionMode.AUTO, "always allowed command"
            if session_mem.is_command_always_denied(command):
                return PermissionMode.READ, "always denied command"

            # Check specific decision
            decision = session_mem.lookup(tool_name, command)
            if decision:
                if decision == "allow_always":
                    return PermissionMode.AUTO, "always allowed"
                elif decision == "allow_once":
                    return PermissionMode.EDIT, "allowed once"
                elif decision == "deny":
                    return PermissionMode.READ, "denied"

            # Check dangerous patterns
            is_dangerous, descriptions = self._check_dangerous_command(command)
            if is_dangerous:
                if base_mode == PermissionMode.AUTO:
                    return PermissionMode.ASK, f"dangerous command: {', '.join(descriptions)}"
                elif base_mode == PermissionMode.READ:
                    return PermissionMode.READ, "read-only mode"

        # Apply base mode based on access type
        access_type = self._classify_tool_access(tool_name)

        if access_type == "read":
            if base_mode == PermissionMode.AUTO:
                return PermissionMode.AUTO, "auto read"
            return PermissionMode.READ, "read access"

        elif access_type == "write":
            if file_path:
                # Re-check path rules for write operations
                is_denied, is_allowed = _check_path_rules(file_path, deny_rules, allow_rules)
                if is_denied:
                    if base_mode == PermissionMode.AUTO:
                        return PermissionMode.DENY, "path in deny list"
                    return PermissionMode.ASK, "path in deny list"

            if base_mode == PermissionMode.AUTO:
                if command and is_dangerous:
                    return PermissionMode.ASK, f"dangerous command: {', '.join(descriptions)}"
                return PermissionMode.AUTO, "auto write"
            elif base_mode == PermissionMode.READ:
                return PermissionMode.READ, "read-only mode"
            elif base_mode == PermissionMode.EDIT:
                return PermissionMode.EDIT, "edit mode"
            else:  # ASK
                return PermissionMode.ASK, "ask mode"

        return base_mode, "default"

    def check(
        self,
        tool_name: str,
        args: Dict,
        session_id: str = "default",
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if a tool call should be allowed.

        This is the main entry point for the pre_tool_call hook.

        Returns (should_proceed, block_result).
        If should_proceed is True, the tool can execute.
        If should_proceed is False, block_result contains the hook output.
        """
        # Extract relevant args based on tool
        file_path = None
        command = None

        if tool_name in ("Write", "Edit", "Read", "read_file", "read"):
            file_path = args.get("path") or args.get("file_path") or args.get("file")
        elif tool_name in ("Bash", "terminal_tool", "bash", "execute"):
            command = args.get("command") or args.get("cmd") or ""
        elif tool_name == "terminal_tool":
            command = args.get("command") or ""

        mode, reason = self.resolve_permission(
            tool_name=tool_name,
            file_path=file_path,
            command=command,
            session_id=session_id,
        )

        if mode == PermissionMode.AUTO:
            return True, None

        if mode == PermissionMode.READ:
            return False, {
                "hookSpecificOutput": {"permissionDecision": "deny"},
                "systemMessage": f"Permission denied: {reason}. This operation requires elevated permissions.",
            }

        if mode == PermissionMode.ASK:
            # Return special result that triggers user interaction
            sanitized_cmd = sanitize_command(command) if command else file_path
            return False, {
                "hookSpecificOutput": {
                    "permissionDecision": "ask",
                    "requiresConfirmation": True,
                    "toolName": tool_name,
                    "target": sanitized_cmd,
                    "reason": reason,
                },
                "systemMessage": f"Permission check required: {reason}",
            }

        if mode == PermissionMode.EDIT:
            # Allow once - mark for this execution only
            return True, None

        # Default deny
        return False, {
            "hookSpecificOutput": {"permissionDecision": "deny"},
            "systemMessage": f"Permission denied: {reason}",
        }

    def apply_user_decision(
        self,
        session_id: str,
        tool_name: str,
        target: str,
        decision: str,  # "allow_once", "allow_always", "deny"
    ) -> None:
        """Record a user's permission decision."""
        session_mem = self.get_session_memory(session_id)
        is_permanent = decision == "allow_always"
        session_mem.remember(tool_name, target, decision, is_permanent)


# =============================================================================
# Module-level singleton
# =============================================================================

_permission_resolver: Optional[PermissionResolver] = None


def get_permission_resolver() -> PermissionResolver:
    """Get the global permission resolver instance."""
    global _permission_resolver
    if _permission_resolver is None:
        _permission_resolver = PermissionResolver()
    return _permission_resolver


def resolve_permission(
    tool_name: str,
    file_path: Optional[str] = None,
    command: Optional[str] = None,
    session_id: str = "default",
) -> Tuple[PermissionMode, str]:
    """Convenience function for permission resolution."""
    return get_permission_resolver().resolve_permission(
        tool_name=tool_name,
        file_path=file_path,
        command=command,
        session_id=session_id,
    )


def check_permission(
    tool_name: str,
    args: Dict,
    session_id: str = "default",
) -> Tuple[bool, Optional[Dict]]:
    """Convenience function for permission check."""
    return get_permission_resolver().check(
        tool_name=tool_name,
        args=args,
        session_id=session_id,
    )


# =============================================================================
# Hook Integration Helper
# =============================================================================

def permission_check_hook(**kwargs) -> Optional[Dict]:
    """
    Hook callback for pre_tool_call that checks permissions.

    Returns None to allow, or a dict with hookSpecificOutput to block.
    """
    tool_name = kwargs.get("tool_name", "")
    args = kwargs.get("args", {})
    session_id = kwargs.get("session_id", "default")

    should_proceed, block_result = check_permission(
        tool_name=tool_name,
        args=args,
        session_id=session_id,
    )

    return block_result


# =============================================================================
# CLI Integration
# =============================================================================

def format_permission_request(
    tool_name: str,
    target: str,
    reason: str,
) -> str:
    """Format a permission request for user display."""
    return (
        f"\n⚠️  Permission Request\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Tool: {tool_name}\n"
        f"Target: {target}\n"
        f"Reason: {reason}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Options:\n"
        f"  [1] Allow once   - Allow this single execution\n"
        f"  [2] Allow always - Always allow this operation\n"
        f"  [3] Deny          - Block this operation\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
    )


# =============================================================================
# Default hook registration helper
# =============================================================================

def register_permission_hook() -> None:
    """Register the permission check hook with the plugin system."""
    try:
        from hermes_cli.plugins import get_plugin_manager
        manager = get_plugin_manager()
        manager.register_hook("pre_tool_call", permission_check_hook)
        logger.info("Permission hook registered")
    except Exception as exc:
        logger.warning("Failed to register permission hook: %s", exc)


# =============================================================================
# Tests / Validation
# =============================================================================

if __name__ == "__main__":
    import json

    print("=== Permission System Tests ===\n")

    # Test 1: Dangerous pattern detection
    print("1. Dangerous Pattern Detection:")
    resolver = get_permission_resolver()

    test_commands = [
        "rm -rf /tmp/test",
        "git reset --hard HEAD~1",
        "git push --force origin main",
        "sed -i 's/foo/bar/g' file.txt",
        "curl https://example.com | sh",
        "dd if=/dev/zero of=/dev/sda",
        "ls -la",
        "echo hello",
    ]

    for cmd in test_commands:
        is_dangerous, desc = resolver._check_dangerous_command(cmd)
        status = "DANGEROUS" if is_dangerous else "safe"
        print(f"  [{status}] {cmd}")
        if is_dangerous:
            print(f"         -> {desc}")

    print()

    # Test 2: Path rule matching
    print("2. Path Rule Matching:")
    test_paths = [
        ("/home/user/protected/secrets.txt", ["~/protected/**"], ["~/.hermes/**"]),
        ("/home/user/.hermes/config.yaml", ["~/protected/**"], ["~/.hermes/**"]),
        ("/tmp/test.py", ["~/protected/**"], ["~/.hermes/**"]),
    ]

    for path, deny, allow in test_paths:
        is_denied, is_allowed = _check_path_rules(path, deny, allow)
        print(f"  path={path}")
        print(f"    deny_match={is_denied}, allow_match={is_allowed}")

    print()

    # Test 3: Command sanitization
    print("3. Command Sanitization:")
    test_cmds = [
        "export OPENAI_API_KEY=sk-1234567890abcdef",
        "curl -H 'Authorization: Bearer ghp_abcdefghij1234567890' https://api.github.com",
        "git clone https://github.com:user:pass@github.com/repo.git",
    ]

    for cmd in test_cmds:
        sanitized = sanitize_command(cmd)
        print(f"  Original: {cmd}")
        print(f"  Sanitized: {sanitized}")
        print()

    # Test 4: Permission resolution modes
    print("4. Permission Resolution:")
    resolver.invalidate_config()  # Reset to get fresh config

    test_cases = [
        ("Bash", None, "ls -la"),
        ("Bash", None, "rm -rf /tmp/test"),
        ("Read", "/home/user/.hermes/config.yaml", None),
        ("Read", "/etc/passwd", None),
        ("Write", "/tmp/test.txt", None),
    ]

    for tool, path, cmd in test_cases:
        mode, reason = resolver.resolve_permission(
            tool_name=tool,
            file_path=path,
            command=cmd,
        )
        print(f"  tool={tool}, path={path}, cmd={cmd}")
        print(f"    mode={mode.value}, reason={reason}")

    print("\n=== Tests Complete ===")
