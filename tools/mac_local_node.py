#!/usr/bin/env python3
"""Mac local-node tool surface and policy helpers.

The Mac local node is intentionally a compact workstation surface.  It is not a
SaaS connector bundle; it exposes six agent-facing tools with action enums and a
Claude Code-like local development policy.  The relay/client implementation can
be layered behind these handlers without changing the public schema.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import shlex
from pathlib import Path
from typing import Any, Iterable

from tools.registry import registry

TOOLSET = "mac_local"

SYSTEM_ACTIONS = ["status"]
FS_ACTIONS = ["read", "search", "write", "patch"]
TERMINAL_ACTIONS = ["run", "start", "poll", "wait", "kill", "input", "exec_code"]
PROJECT_CONTEXT_ACTIONS = ["summarize"]
UI_ACTIONS = ["screenshot", "open", "clipboard", "osascript"]
AGENT_ACTIONS = ["spawn", "status", "logs", "kill"]

# Keep these as data so tests can assert the intentionally small surface.
REMOVED_STANDALONE_TOOL_NAMES = frozenset(
    {
        "mac_status",
        "mac_capabilities",
        "mac_read_file",
        "mac_search_files",
        "mac_write_file",
        "mac_patch",
        "mac_process_start",
        "mac_process_poll",
        "mac_process_wait",
        "mac_process_kill",
        "mac_process_input",
        "mac_execute_code",
        "mac_git_status",
        "mac_git_diff",
        "mac_git_commit",
        "mac_screenshot",
        "mac_browser",  # direct browser is deferred in V1
        "mac_clipboard",
        "mac_open",
        "mac_osascript",
        "mac_spawn_agent",
        "mac_agent_status",
        "mac_agent_logs",
        "mac_agent_kill",
    }
)


@dataclass(frozen=True)
class PolicyVerdict:
    """Decision returned by the Mac local-node policy classifier."""

    decision: str  # allow | ask | deny
    reason: str
    scope: str = "unknown"


@dataclass(frozen=True)
class TrustedRoot:
    """Trusted local root known to the Mac local-node policy."""

    path: str
    scope: str

    @property
    def canonical(self) -> str:
        expanded = os.path.expanduser(os.path.expandvars(self.path))
        return _normalize_path_for_policy(expanded)


class MacLocalPolicy:
    """Claude Code-like policy for local Mac workstation actions.

    The policy is intentionally flexible inside trusted roots: local dev reads,
    writes, patches, tests, builds, background processes, local commits, and
    worker agents are allowed.  It asks only for actions with real risk:
    external/publicating side effects, broad destructive operations, global or
    privileged system changes, secrets, or paths outside trusted roots.
    """

    secret_name_patterns = (
        re.compile(r"(^|/)\.env($|[./*?\[\]{},'\")\s])"),
        re.compile(r"(^|/)\.npmrc($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|/)\.pypirc($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|/)\.netrc($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|/)\.aws/credentials($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|/)id_(rsa|dsa|ecdsa|ed25519)($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|/)\.ssh(/|$)"),
        re.compile(r"(^|/)Library/Keychains(/|$)"),
        re.compile(r"(^|/)Keychains(/|$)"),
        re.compile(r"(^|/)(Cookies|Login Data|Local State)$"),
        re.compile(r"(^|/)(auth|token|credentials?)-?cache(/|$)", re.I),
        re.compile(r"(^|/)\.config/gh/hosts\.yml($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|/)\.git-credentials($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|/)\.docker/config\.json($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|/)\.config/gcloud/application_default_credentials\.json($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|/)\.kube/config($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|/)\.codex(/|$)"),
        re.compile(r"(^|/)\.claude(/|$)"),
        re.compile(r"(^|/)\.mcp-auth[^/]*(/|$)"),
    )

    destructive_patterns = (
        re.compile(r"\brm\s+-[^\n;|&]*r[^\n;|&]*\b"),
        re.compile(r"\bgit\b.*\breset\s+--hard\b"),
        re.compile(r"\bgit\b.*\bclean\s+-[^\n;|&]*[fdx][^\n;|&]*\b"),
        re.compile(r"\bgit\b.*\bpush\b.*\s--force(?:-with-lease)?\b"),
        re.compile(r"\bdocker\b.*\bcompose\b.*\bdown\b.*\s-v\b"),
        re.compile(r"\bdocker\b.*\bcompose\b.*\brm\b.*-[A-Za-z]*[svf][A-Za-z]*\b"),
        re.compile(r"\bdocker\b.*\b(system|volume)\s+(rm|prune)\b"),
        re.compile(r"\b(dd|mkfs|diskutil)\b"),
    )

    external_patterns = (
        re.compile(r"\bgit\b.*\bpush\b"),
        re.compile(r"\bgh\b.*\bpr\s+(create|comment|review|merge)\b"),
        re.compile(r"\bgh\b.*\bissue\s+(create|comment|edit|close|reopen)\b"),
        re.compile(r"\bgh\b.*\brelease\s+(create|upload|delete)\b"),
        re.compile(r"\brailway\s+(deploy|up|variables\s+set)\b"),
        re.compile(r"\b(vercel|netlify|flyctl)\s+(deploy|publish)\b"),
        re.compile(r"\bnpm\s+publish\b"),
        re.compile(r"\b(pnpm|yarn)\s+publish\b"),
        re.compile(r"\b(curl|wget)\b.*(--data|--data-binary|--post-file|-d|-F|-T|--upload-file|-X\s*POST|-X\s*PUT)", re.I),
        re.compile(r"\b(scp|rsync|nc|netcat|ssh|sftp|ftp)\b"),
    )

    global_or_privileged_patterns = (
        re.compile(r"\bsudo\b"),
        re.compile(r"\b(chmod|chown)\s+-R\b"),
        re.compile(r"\bbrew\s+(install|upgrade|remove)\b"),
        re.compile(r"\bnpm\s+install\s+-g\b"),
        re.compile(r"\bpip\s+install\s+(--user|-U|--upgrade)\b"),
    )

    guarded_mac_surface_patterns = (
        re.compile(r"\bsecurity\b"),
        re.compile(r"\bosascript\b"),
        re.compile(r"\bpb(paste|copy)\b"),
    )

    broad_secret_discovery_patterns = (
        re.compile(r"\b(cat|less|more|head|tail)\s+\.\*"),
        re.compile(r"\b(grep|rg)\b.*\b(token|secret|password|credential|api[_-]?key)\b.*\s\.($|\s)"),
        re.compile(r"\bfind\s+\.(?:\s|$).*-name\s+['\"]?\.(env|npmrc|pypirc|netrc)\b"),
        re.compile(r"\bfind\s+\.(?:\s|$).*-type\s+f\b"),
        re.compile(r"\btar\b.*\s\.($|\s)"),
    )

    relative_secret_command_patterns = (
        re.compile(r"(^|[\s'\"(])\.env($|[./*?\[\]{},'\")\s])"),
        re.compile(r"(^|[\s'\"(])\.aws/credentials($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|[\s'\"(])\.npmrc($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|[\s'\"(])\.pypirc($|[/*?\[\]{},'\")\s])"),
        re.compile(r"(^|[\s'\"(])\.netrc($|[/*?\[\]{},'\")\s])"),
    )

    def __init__(self, trusted_roots: Iterable[TrustedRoot]):
        self.trusted_roots = tuple(trusted_roots)

    @classmethod
    def default(cls) -> "MacLocalPolicy":
        return cls(
            [
                TrustedRoot("~/personal-projects", "personal"),
                TrustedRoot("~/projects", "personal"),
                TrustedRoot("~/Documents", "personal"),
                TrustedRoot("~/Downloads", "personal"),
                TrustedRoot("~/Desktop", "personal"),
                TrustedRoot("~/Obsidian", "personal"),
                # Rafael/Pazzi's work scope: paggo-project is mounted/exposed as /work.
                TrustedRoot("/work", "work"),
                TrustedRoot("/tmp", "scratch"),
            ]
        )

    def classify_path(self, path: str, action: str) -> PolicyVerdict:
        normalized = _normalize_path_for_policy(path)
        if self._is_secret_path(normalized):
            return PolicyVerdict("deny", "SECRET_DENIED", self._scope_for_path(normalized))
        scope = self._scope_for_path(normalized)
        if scope == "unknown":
            return PolicyVerdict("ask", "APPROVAL_REQUIRED", scope)
        if action in {"read", "search", "write", "patch", "screenshot", "open", "spawn"}:
            return PolicyVerdict("allow", "TRUSTED_ROOT", scope)
        return PolicyVerdict("ask", "APPROVAL_REQUIRED", scope)

    def classify_command(self, command: str, cwd: str | None = None) -> PolicyVerdict:
        cwd_scope = self._scope_for_path(_normalize_path_for_policy(cwd or os.getcwd()))
        if cwd_scope == "unknown":
            return PolicyVerdict("ask", "APPROVAL_REQUIRED", cwd_scope)

        compact = " ".join(command.strip().split())
        if not compact:
            return PolicyVerdict("deny", "EMPTY_COMMAND", cwd_scope)
        if self._matches_any(compact, self.broad_secret_discovery_patterns):
            return PolicyVerdict("ask", "APPROVAL_REQUIRED", cwd_scope)
        if self._command_mentions_secret(compact):
            return PolicyVerdict("deny", "SECRET_DENIED", cwd_scope)
        if self._command_mentions_untrusted_path(compact, cwd or os.getcwd()):
            return PolicyVerdict("ask", "APPROVAL_REQUIRED", cwd_scope)
        if self._matches_any(compact, self.destructive_patterns):
            return PolicyVerdict("ask", "APPROVAL_REQUIRED", cwd_scope)
        if self._matches_any(compact, self.external_patterns):
            return PolicyVerdict("ask", "APPROVAL_REQUIRED", cwd_scope)
        if self._matches_any(compact, self.global_or_privileged_patterns):
            return PolicyVerdict("ask", "APPROVAL_REQUIRED", cwd_scope)
        if self._matches_any(compact, self.guarded_mac_surface_patterns):
            return PolicyVerdict("ask", "APPROVAL_REQUIRED", cwd_scope)
        return PolicyVerdict("allow", "LOCAL_DEV_ALLOWED", cwd_scope)

    def _is_secret_path(self, normalized: str) -> bool:
        # Explicit examples are safe to read/write in repos.
        if normalized.endswith("/.env.example") or normalized.endswith("/.env.sample"):
            return False
        return self._contains_secret_path_text(normalized)

    def _contains_secret_path_text(self, text: str) -> bool:
        normalized = text.replace("\\\\", "/")
        return any(pattern.search(normalized) for pattern in self.secret_name_patterns)

    def _command_mentions_secret(self, command: str) -> bool:
        if self._contains_secret_path_text(command):
            return True
        if any(self._is_secret_path(_normalize_path_for_policy(path)) for path in _absolute_path_mentions(command)):
            return True
        if self._matches_any(command, self.relative_secret_command_patterns):
            return True
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
        return any(self._is_secret_path(_normalize_path_for_policy(part)) for part in parts)

    def _command_mentions_untrusted_path(self, command: str, cwd: str) -> bool:
        cwd_path = _normalize_path_for_policy(cwd)
        candidates = set(_absolute_path_mentions(command))
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
        for part in parts:
            cleaned = _clean_command_path_token(part)
            if not cleaned:
                continue
            expanded = _expand_command_path_token(cleaned, cwd_path)
            candidates.update(_absolute_path_mentions(expanded))
            if expanded.startswith("/"):
                candidates.add(expanded)
            elif expanded.startswith("../") or expanded == ".." or "/../" in expanded:
                candidates.add(str(Path(cwd_path, expanded)))
        return any(self._scope_for_path(_normalize_path_for_policy(candidate)) == "unknown" for candidate in candidates)

    def _scope_for_path(self, normalized: str) -> str:
        for root in self.trusted_roots:
            canonical = root.canonical
            if normalized == canonical or normalized.startswith(canonical.rstrip("/") + "/"):
                return root.scope
        return "unknown"

    @staticmethod
    def _matches_any(command: str, patterns: Iterable[re.Pattern[str]]) -> bool:
        return any(pattern.search(command) for pattern in patterns)


def _normalize_path_for_policy(path: str) -> str:
    if not path:
        return ""
    expanded = os.path.expanduser(os.path.expandvars(path))
    try:
        return os.path.normpath(str(Path(expanded).resolve(strict=False)))
    except (OSError, RuntimeError, ValueError):
        return os.path.normpath(expanded)


def _absolute_path_mentions(text: str) -> list[str]:
    mentions = re.findall(r"(?<![\w@.-])(/[^\s'\"`<>|&;,)\]]+)", text)
    return [_clean_command_path_token(mention) for mention in mentions]


def _clean_command_path_token(token: str) -> str:
    cleaned = token.strip().strip("'\"`()[]{}<>,;|&")
    if cleaned.startswith("@/"):
        cleaned = cleaned[1:]
    return cleaned


def _expand_command_path_token(token: str, cwd: str) -> str:
    """Expand shell path variables that would otherwise hide path escapes."""

    expanded = token.replace("${PWD}", cwd).replace("$PWD", cwd)
    expanded = os.path.expanduser(os.path.expandvars(expanded))
    return expanded


def _action_schema(actions: list[str], *, extra_properties: dict[str, Any] | None = None) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "action": {
            "type": "string",
            "enum": actions,
            "description": "Action to perform within this compact Mac local-node tool.",
        },
        "response_format": {
            "type": "string",
            "enum": ["concise", "detailed"],
            "description": "Return compact output by default; use detailed only when follow-up IDs/metadata are needed.",
            "default": "concise",
        },
    }
    if extra_properties:
        properties.update(extra_properties)
    return {
        "type": "object",
        "properties": properties,
        "required": ["action"],
        "additionalProperties": False,
    }


def _tool_schema(name: str, description: str, actions: list[str], extra_properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": _action_schema(actions, extra_properties=extra_properties),
    }


def get_mac_local_tool_schemas() -> dict[str, dict[str, Any]]:
    """Return the intentionally compact six-tool Mac local-node schema map."""

    return {
        "mac_system": _tool_schema(
            "mac_system",
            "Use this when you need Mac online state, trusted roots, policy mode, and current local-node capabilities.",
            SYSTEM_ACTIONS,
        ),
        "mac_fs": _tool_schema(
            "mac_fs",
            "Use this when you need token-efficient Mac file read/search/write/patch with path and secret policy.",
            FS_ACTIONS,
            {
                "path": {"type": "string", "description": "File or directory path on the Mac."},
                "pattern": {"type": "string", "description": "Search pattern or patch/find text."},
                "content": {"type": "string", "description": "New file content or replacement text."},
                "offset": {"type": "integer", "minimum": 1, "description": "1-indexed line offset for reads."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 2000, "description": "Maximum lines/results to return."},
            },
        ),
        "mac_terminal": _tool_schema(
            "mac_terminal",
            "Use this when you need Mac shell, managed processes, stdin, or short local Python/JS code execution.",
            TERMINAL_ACTIONS,
            {
                "command": {"type": "string", "description": "Shell command for run/start actions."},
                "cwd": {"type": "string", "description": "Working directory on the Mac."},
                "process_id": {"type": "string", "description": "Managed process handle for poll/wait/kill/input."},
                "data": {"type": "string", "description": "Input text or code payload."},
                "language": {"type": "string", "enum": ["python", "javascript", "bash"], "description": "Language for exec_code."},
                "timeout": {"type": "integer", "minimum": 1, "maximum": 3600, "description": "Timeout in seconds."},
            },
        ),
        "mac_project_context": _tool_schema(
            "mac_project_context",
            "Use this when you need one compact preflight summary of a Mac project/repo before editing or testing.",
            PROJECT_CONTEXT_ACTIONS,
            {"path": {"type": "string", "description": "Project or repository path on the Mac."}},
        ),
        "mac_ui": _tool_schema(
            "mac_ui",
            "Use this when you need Mac screenshot, open, clipboard, or guarded AppleScript/JXA automation.",
            UI_ACTIONS,
            {
                "target": {"type": "string", "description": "URL, file, app, clipboard text, or AppleScript/JXA target."},
                "data": {"type": "string", "description": "Clipboard text or script body."},
            },
        ),
        "mac_agent": _tool_schema(
            "mac_agent",
            "Use this when you need to spawn, inspect, stream logs from, or stop a local Codex/Claude/OpenCode/Pi worker.",
            AGENT_ACTIONS,
            {
                "kind": {"type": "string", "enum": ["codex", "claude", "opencode", "pi"], "description": "Local worker to use when spawning."},
                "mode": {"type": "string", "enum": ["read_only", "review", "dev_autonomous"], "description": "Worker permission posture."},
                "workdir": {"type": "string", "description": "Trusted Mac workdir/worktree."},
                "prompt": {"type": "string", "description": "Task prompt for spawn."},
                "agent_id": {"type": "string", "description": "Worker handle for status/logs/kill."},
            },
        ),
    }


def get_action_enum(schema: dict[str, Any]) -> list[str]:
    """Return a schema's action enum; small helper used by tests/docs."""

    return list(schema["parameters"]["properties"]["action"]["enum"])


def check_mac_local_node_requirements() -> bool:
    """Return True so enabled mac_local tools stay discoverable offline.

    The mac_local toolset is opt-in, so availability should be controlled by
    toolset selection.  Once selected, handlers return structured MAC_OFFLINE
    errors when no node URL/relay is configured instead of disappearing from the
    model's schema list.
    """

    return True


def _mac_node_configured() -> bool:
    enabled = os.getenv("HERMES_MAC_LOCAL_NODE_ENABLED", "").lower() in {"1", "true", "yes", "on"}
    return enabled or bool(os.getenv("HERMES_MAC_LOCAL_NODE_URL"))


def _offline_result(tool: str, action: str | None) -> str:
    return json.dumps(
        {
            "ok": False,
            "error_code": "MAC_OFFLINE",
            "message": "Mac local node is not configured or is offline.",
            "tool": tool,
            "action": action,
        }
    )


def _extract_action(args: dict[str, Any] | None) -> str | None:
    if not isinstance(args, dict):
        return None
    action = args.get("action")
    return action if isinstance(action, str) else None


def _handle_placeholder(tool: str, args: dict[str, Any] | None) -> str:
    action = _extract_action(args)
    if not _mac_node_configured():
        return _offline_result(tool, action)
    return json.dumps(
        {
            "ok": False,
            "error_code": "NOT_IMPLEMENTED",
            "message": "Mac local node relay is configured, but this action has not been wired yet.",
            "tool": tool,
            "action": action,
        }
    )


def handle_mac_system(args: dict[str, Any] | None = None, **_: Any) -> str:
    return _handle_placeholder("mac_system", args)


def handle_mac_fs(args: dict[str, Any] | None = None, **_: Any) -> str:
    return _handle_placeholder("mac_fs", args)


def handle_mac_terminal(args: dict[str, Any] | None = None, **_: Any) -> str:
    return _handle_placeholder("mac_terminal", args)


def handle_mac_project_context(args: dict[str, Any] | None = None, **_: Any) -> str:
    return _handle_placeholder("mac_project_context", args)


def handle_mac_ui(args: dict[str, Any] | None = None, **_: Any) -> str:
    return _handle_placeholder("mac_ui", args)


def handle_mac_agent(args: dict[str, Any] | None = None, **_: Any) -> str:
    return _handle_placeholder("mac_agent", args)


_SCHEMAS = get_mac_local_tool_schemas()


registry.register(
    name="mac_system",
    toolset=TOOLSET,
    schema=_SCHEMAS["mac_system"],
    handler=lambda args, **kwargs: handle_mac_system(args, **kwargs),
    check_fn=check_mac_local_node_requirements,
    emoji="🖥️",
    max_result_size_chars=50_000,
)
registry.register(
    name="mac_fs",
    toolset=TOOLSET,
    schema=_SCHEMAS["mac_fs"],
    handler=lambda args, **kwargs: handle_mac_fs(args, **kwargs),
    check_fn=check_mac_local_node_requirements,
    emoji="🖥️",
    max_result_size_chars=50_000,
)
registry.register(
    name="mac_terminal",
    toolset=TOOLSET,
    schema=_SCHEMAS["mac_terminal"],
    handler=lambda args, **kwargs: handle_mac_terminal(args, **kwargs),
    check_fn=check_mac_local_node_requirements,
    emoji="🖥️",
    max_result_size_chars=50_000,
)
registry.register(
    name="mac_project_context",
    toolset=TOOLSET,
    schema=_SCHEMAS["mac_project_context"],
    handler=lambda args, **kwargs: handle_mac_project_context(args, **kwargs),
    check_fn=check_mac_local_node_requirements,
    emoji="🖥️",
    max_result_size_chars=50_000,
)
registry.register(
    name="mac_ui",
    toolset=TOOLSET,
    schema=_SCHEMAS["mac_ui"],
    handler=lambda args, **kwargs: handle_mac_ui(args, **kwargs),
    check_fn=check_mac_local_node_requirements,
    emoji="🖥️",
    max_result_size_chars=50_000,
)
registry.register(
    name="mac_agent",
    toolset=TOOLSET,
    schema=_SCHEMAS["mac_agent"],
    handler=lambda args, **kwargs: handle_mac_agent(args, **kwargs),
    check_fn=check_mac_local_node_requirements,
    emoji="🖥️",
    max_result_size_chars=50_000,
)
