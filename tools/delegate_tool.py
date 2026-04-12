#!/usr/bin/env python3
"""
Delegate Tool -- Subagent Architecture

Spawns child AIAgent instances with isolated context, restricted toolsets,
and their own terminal sessions. Supports single-task and batch (parallel)
modes. The parent blocks until all children complete.

Each child gets:
  - A fresh conversation (no parent history)
  - Its own task_id (own terminal session, file ops cache)
  - A restricted toolset (configurable, with blocked tools always stripped)
  - A focused system prompt built from the delegated goal + context

The parent's context only sees the delegation call and the summary result,
never the child's intermediate tool calls or reasoning.
"""

import hashlib
import json
import logging
logger = logging.getLogger(__name__)
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from toolsets import TOOLSETS


# Tools that children must never have access to
DELEGATE_BLOCKED_TOOLS = frozenset([
    "delegate_task",   # no recursive delegation
    "clarify",         # no user interaction
    "memory",          # no writes to shared MEMORY.md
    "send_message",    # no cross-platform side effects
    "execute_code",    # children should reason step-by-step, not write scripts
])

# Build a description fragment listing toolsets available for subagents.
# Excludes toolsets where ALL tools are blocked, composite/platform toolsets
# (hermes-* prefixed), and scenario toolsets.
_EXCLUDED_TOOLSET_NAMES = frozenset({"debugging", "safe", "delegation", "moa", "rl"})
_SUBAGENT_TOOLSETS = sorted(
    name for name, defn in TOOLSETS.items()
    if name not in _EXCLUDED_TOOLSET_NAMES
    and not name.startswith("hermes-")
    and not all(t in DELEGATE_BLOCKED_TOOLS for t in defn.get("tools", []))
)
_TOOLSET_LIST_STR = ", ".join(f"'{n}'" for n in _SUBAGENT_TOOLSETS)

_DEFAULT_MAX_CONCURRENT_CHILDREN = 3
_DEFAULT_WORKER_LEASE_TTL_SECONDS = 1800
MAX_DEPTH = 2  # parent (0) -> child (1) -> grandchild rejected (2)


def _get_max_concurrent_children() -> int:
    """Read delegation.max_concurrent_children from config, falling back to
    DELEGATION_MAX_CONCURRENT_CHILDREN env var, then the default (3).

    Uses the same ``_load_config()`` path that the rest of ``delegate_task``
    uses, keeping config priority consistent (config.yaml > env > default).
    """
    cfg = _load_config()
    val = cfg.get("max_concurrent_children")
    if val is not None:
        try:
            return max(1, int(val))
        except (TypeError, ValueError):
            logger.warning(
                "delegation.max_concurrent_children=%r is not a valid integer; "
                "using default %d", val, _DEFAULT_MAX_CONCURRENT_CHILDREN,
            )
    env_val = os.getenv("DELEGATION_MAX_CONCURRENT_CHILDREN")
    if env_val:
        try:
            return max(1, int(env_val))
        except (TypeError, ValueError):
            pass
    return _DEFAULT_MAX_CONCURRENT_CHILDREN
DEFAULT_MAX_ITERATIONS = 50
_HEARTBEAT_INTERVAL = 30  # seconds between parent activity heartbeats during delegation
DEFAULT_TOOLSETS = ["terminal", "file", "web"]


def check_delegate_requirements() -> bool:
    """Delegation has no external requirements -- always available."""
    return True


def _build_child_system_prompt(
    goal: str,
    context: Optional[str] = None,
    *,
    workspace_path: Optional[str] = None,
    execution_envelope: Optional[Dict[str, Any]] = None,
    context_package: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a focused system prompt for a child agent."""
    parts = [
        "You are a focused subagent working on a specific delegated task.",
        "",
        f"YOUR TASK:\n{goal}",
    ]
    if context and context.strip():
        parts.append(f"\nCONTEXT:\n{context}")
    if context_package:
        parts.append(f"\nCONTEXT PACKAGE:\n{_render_structured_block(context_package)}")
    if execution_envelope:
        parts.append(f"\nEXECUTION ENVELOPE:\n{_render_structured_block(execution_envelope)}")
    if workspace_path and str(workspace_path).strip():
        parts.append(
            "\nWORKSPACE PATH:\n"
            f"{workspace_path}\n"
            "Use this exact path for local repository/workdir operations unless the task explicitly says otherwise."
        )
    parts.append(
        "\nComplete this task using the tools available to you. "
        "When finished, provide a clear, concise summary of:\n"
        "- What you did\n"
        "- What you found or accomplished\n"
        "- Any files you created or modified\n"
        "- Any issues encountered\n\n"
        "Important workspace rule: Never assume a repository lives at /workspace/... or any other container-style path unless the task/context explicitly gives that path. "
        "If no exact local path is provided, discover it first before issuing git/workdir-specific commands.\n\n"
        "If an execution envelope is provided, treat its completion criteria and artifact schema as part of the contract for this task.\n\n"
        "Be thorough but concise -- your response is returned to the "
        "parent agent as a summary."
    )
    return "\n".join(parts)


def _resolve_workspace_hint(parent_agent) -> Optional[str]:
    """Best-effort local workspace hint for child prompts.

    We only inject a path when we have a concrete absolute directory. This avoids
    teaching subagents a fake container path while still helping them avoid
    guessing `/workspace/...` for local repo tasks.
    """
    candidates = [
        os.getenv("TERMINAL_CWD"),
        getattr(getattr(parent_agent, "_subdirectory_hints", None), "working_dir", None),
        getattr(parent_agent, "terminal_cwd", None),
        getattr(parent_agent, "cwd", None),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            text = os.path.abspath(os.path.expanduser(str(candidate)))
        except Exception:
            continue
        if os.path.isabs(text) and os.path.isdir(text):
            return text
    return None


def _sanitize_jsonish(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            cleaned = _sanitize_jsonish(item)
            if cleaned is not None:
                sanitized[str(key)] = cleaned
        return sanitized
    if isinstance(value, (list, tuple, set)):
        sanitized_items = []
        for item in value:
            cleaned = _sanitize_jsonish(item)
            if cleaned is not None:
                sanitized_items.append(cleaned)
        return sanitized_items
    return None


def _render_structured_block(payload: Optional[Dict[str, Any]]) -> str:
    safe_payload = _sanitize_jsonish(payload) or {}
    return json.dumps(safe_payload, indent=2, ensure_ascii=False, sort_keys=True)


def _classify_tool_message_status(content: Any) -> str:
    text = content if isinstance(content, str) else str(content or "")
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            payload = json.loads(stripped)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            status_value = str(payload.get("status") or "").strip().lower()
            if status_value in {"blocked", "error", "disabled", "approval_required"}:
                return "error"
            exit_code = payload.get("exit_code")
            if isinstance(exit_code, bool):
                exit_code = int(exit_code)
            if isinstance(exit_code, int) and exit_code != 0:
                return "error"
            error_value = payload.get("error")
            if error_value not in (None, "", []):
                return "error"
            return "ok"
    return "error" if (stripped and "error" in stripped[:80].lower()) else "ok"


def _resolve_direct_terminal_work_order(
    execution_envelope: Optional[Dict[str, Any]],
    capability_snapshot: Optional[Dict[str, Any]],
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    envelope = execution_envelope if isinstance(execution_envelope, dict) else {}
    execution_mode = str(envelope.get("execution_mode") or "").strip()
    if execution_mode != "direct_terminal_work_order":
        return None, None

    effective_toolsets = sorted({
        str(toolset).strip()
        for toolset in ((capability_snapshot or {}).get("effective_toolsets") or [])
        if str(toolset).strip()
    })
    if effective_toolsets != ["terminal"]:
        return None, "direct_terminal_work_order requires exactly the terminal toolset"

    payload = envelope.get("direct_terminal_work_order")
    if not isinstance(payload, dict):
        return None, "direct_terminal_work_order payload is missing"

    command = payload.get("command")
    if not isinstance(command, str) or not command.strip():
        return None, "direct_terminal_work_order requires a non-empty command"

    timeout_seconds = payload.get("timeout_seconds")
    if timeout_seconds is not None:
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            return None, "direct_terminal_work_order timeout_seconds must be an integer"
        if timeout_seconds <= 0:
            return None, "direct_terminal_work_order timeout_seconds must be > 0"

    workdir = payload.get("workdir")
    if workdir is not None:
        workdir = str(workdir).strip() or None

    return {
        "command": command,
        "timeout_seconds": timeout_seconds,
        "workdir": workdir,
    }, None


def _resolve_child_toolsets(parent_agent, requested_toolsets: Optional[List[str]]) -> List[str]:
    """Resolve the deterministic child tool surface from parent + request."""
    parent_enabled = getattr(parent_agent, "enabled_toolsets", None)
    if not isinstance(parent_enabled, (list, tuple, set)):
        parent_enabled = None

    valid_tool_names = getattr(parent_agent, "valid_tool_names", None)
    if not isinstance(valid_tool_names, (list, tuple, set)):
        valid_tool_names = None

    if parent_enabled is not None:
        parent_toolsets = set(parent_enabled)
    elif valid_tool_names is not None:
        import model_tools
        parent_toolsets = {
            ts for name in valid_tool_names
            if (ts := model_tools.get_toolset_for_tool(name)) is not None
        }
    else:
        parent_toolsets = set(DEFAULT_TOOLSETS)

    if requested_toolsets:
        return _strip_blocked_tools([t for t in requested_toolsets if t in parent_toolsets])
    if parent_agent and parent_enabled is not None:
        return _strip_blocked_tools(parent_enabled)
    if parent_toolsets:
        return _strip_blocked_tools(sorted(parent_toolsets))
    return _strip_blocked_tools(DEFAULT_TOOLSETS)


def _build_context_package(
    goal: str,
    context: Optional[str],
    parent_agent,
    workspace_path: Optional[str],
    requested_toolsets: Optional[List[str]],
    effective_toolsets: List[str],
    context_package: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    package: Dict[str, Any] = _sanitize_jsonish({
        "goal": goal,
        "workspace_path": workspace_path,
        "parent_session_id": getattr(parent_agent, "session_id", None),
        "requested_toolsets": list(requested_toolsets or []),
        "effective_toolsets": list(effective_toolsets),
    }) or {}
    if context and context.strip():
        package["user_context"] = context.strip()
    user_package = _sanitize_jsonish(context_package) or {}
    if isinstance(user_package, dict):
        package.update(user_package)
    return package


def _build_execution_envelope(
    goal: str,
    capability_snapshot: Dict[str, Any],
    context_package: Dict[str, Any],
    execution_envelope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    envelope = _sanitize_jsonish(dict(execution_envelope or {})) if isinstance(execution_envelope, dict) else {}
    envelope = envelope or {}
    envelope.setdefault("task_spec", goal)
    envelope.setdefault(
        "completion_criteria",
        [
            "Summarize what was accomplished.",
            "List files created or modified.",
            "Call out blockers or fallback reasons if the task did not fully complete.",
        ],
    )
    envelope.setdefault("artifact_schema", {"required": ["summary"], "optional": ["files_modified", "issues"]})
    envelope["capability_snapshot"] = _sanitize_jsonish(capability_snapshot) or {}
    envelope["context_package"] = _sanitize_jsonish(context_package) or {}
    return envelope


def _strip_blocked_tools(toolsets: List[str]) -> List[str]:
    """Remove toolsets that contain only blocked tools."""
    blocked_toolset_names = {
        "delegation", "clarify", "memory", "code_execution",
    }
    return [t for t in toolsets if t not in blocked_toolset_names]


def _get_worker_lease_policy(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = cfg or _load_config()
    enabled_raw = cfg.get("worker_lease_reuse")
    if enabled_raw is None:
        enabled_raw = os.getenv("DELEGATION_WORKER_LEASE_REUSE", "false")
    ttl_raw = cfg.get("worker_lease_ttl_seconds")
    if ttl_raw is None:
        ttl_raw = os.getenv("DELEGATION_WORKER_LEASE_TTL_SECONDS", str(_DEFAULT_WORKER_LEASE_TTL_SECONDS))
    try:
        ttl_seconds = max(1, int(float(ttl_raw)))
    except (TypeError, ValueError):
        ttl_seconds = _DEFAULT_WORKER_LEASE_TTL_SECONDS
    enabled = str(enabled_raw).strip().lower() in {"1", "true", "yes", "on"}
    return {
        "enabled": enabled,
        "ttl_seconds": ttl_seconds,
    }


def _supports_worker_lease(toolsets: List[str]) -> bool:
    normalized = sorted({str(toolset).strip() for toolset in (toolsets or []) if str(toolset).strip()})
    return normalized == ["terminal"]


def _ensure_delegate_worker_lease_state(parent_agent) -> tuple[dict[str, Any], threading.Lock]:
    leases = getattr(parent_agent, "_delegate_worker_leases", None)
    lock = getattr(parent_agent, "_delegate_worker_leases_lock", None)
    if leases is None:
        leases = {}
        setattr(parent_agent, "_delegate_worker_leases", leases)
    if lock is None:
        lock = threading.Lock()
        setattr(parent_agent, "_delegate_worker_leases_lock", lock)
    return leases, lock


def _terminal_backend_snapshot() -> Dict[str, Any]:
    return {
        "env_type": os.getenv("TERMINAL_ENV", "local"),
        "docker_image": os.getenv("TERMINAL_DOCKER_IMAGE"),
        "docker_mount_cwd_to_workspace": os.getenv("TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE"),
        "terminal_cwd": os.getenv("TERMINAL_CWD"),
        "container_persistent": os.getenv("TERMINAL_CONTAINER_PERSISTENT"),
        "modal_mode": os.getenv("TERMINAL_MODAL_MODE"),
    }


def _build_delegate_worker_lease_key(
    parent_agent,
    *,
    toolsets: List[str],
    model: Optional[str],
    provider: Optional[str],
    base_url: Optional[str],
    api_mode: Optional[str],
    workspace_path: Optional[str],
) -> str:
    parent_session_id = getattr(parent_agent, "session_id", None) or f"parent-{id(parent_agent)}"
    blob = json.dumps(
        {
            "parent_session_id": parent_session_id,
            "toolsets": sorted(toolsets or []),
            "model": model,
            "provider": provider,
            "base_url": base_url,
            "api_mode": api_mode,
            "workspace_path": workspace_path,
            "terminal_backend": _terminal_backend_snapshot(),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def _build_delegate_worker_assignment(
    parent_agent,
    *,
    cfg: Dict[str, Any],
    task_count: int,
    toolsets: List[str],
    model: Optional[str],
    provider: Optional[str],
    base_url: Optional[str],
    api_mode: Optional[str],
    workspace_path: Optional[str],
) -> Dict[str, Any]:
    policy = _get_worker_lease_policy(cfg)
    cold_assignment = {
        "task_id": f"delegate-cold-{uuid.uuid4().hex[:12]}",
        "worker_mode": "cold",
        "keep_warm": False,
        "lease_key": None,
        "reused": False,
        "reuse_count": 0,
        "ttl_seconds": policy["ttl_seconds"],
        "lease_age_seconds": 0.0,
    }
    if task_count != 1 or not policy["enabled"] or not _supports_worker_lease(toolsets):
        return cold_assignment

    lease_key = _build_delegate_worker_lease_key(
        parent_agent,
        toolsets=toolsets,
        model=model,
        provider=provider,
        base_url=base_url,
        api_mode=api_mode,
        workspace_path=workspace_path,
    )
    leases, lock = _ensure_delegate_worker_lease_state(parent_agent)
    now = time.time()
    with lock:
        expired = [
            key for key, lease in leases.items()
            if now - float(lease.get("last_used_at", lease.get("created_at", now))) > policy["ttl_seconds"]
        ]
        for key in expired:
            leases.pop(key, None)
        lease = leases.get(lease_key)
        if lease is None:
            lease = {
                "task_id": f"delegate-lease-{lease_key}",
                "created_at": now,
                "last_used_at": now,
                "reuse_count": 0,
            }
            leases[lease_key] = lease
            reused = False
        else:
            reused = True
            lease["last_used_at"] = now
            lease["reuse_count"] = int(lease.get("reuse_count", 0)) + 1
        lease_age_seconds = round(now - float(lease.get("created_at", now)), 2)
        return {
            "task_id": lease["task_id"],
            "worker_mode": "warm" if reused else "lease_prime",
            "keep_warm": True,
            "lease_key": lease_key,
            "reused": reused,
            "reuse_count": int(lease.get("reuse_count", 0)),
            "ttl_seconds": policy["ttl_seconds"],
            "lease_age_seconds": lease_age_seconds,
        }


def _capture_worker_runtime_metadata(parent_agent, worker_assignment: Dict[str, Any]) -> Dict[str, Any]:
    worker_task_id = worker_assignment.get("task_id")
    worker_keep_warm = bool(worker_assignment.get("keep_warm"))
    worker_lease_key = worker_assignment.get("lease_key")
    runtime_id = None
    runtime_kind = None
    try:
        from tools.terminal_tool import get_active_env
        env = get_active_env(worker_task_id)
        if env is not None:
            runtime_kind = type(env).__name__
            runtime_id = (
                getattr(env, "_container_id", None)
                or getattr(env, "_sandbox_id", None)
                or getattr(env, "instance_id", None)
                or getattr(env, "_task_id", None)
            )
    except Exception:
        pass

    runtime_reused = False
    if worker_keep_warm and worker_lease_key:
        leases, lock = _ensure_delegate_worker_lease_state(parent_agent)
        with lock:
            lease = leases.get(worker_lease_key)
            previous_runtime_id = lease.get("runtime_id") if isinstance(lease, dict) else None
            runtime_reused = bool(runtime_id and previous_runtime_id and runtime_id == previous_runtime_id)
            if isinstance(lease, dict):
                if runtime_id:
                    lease["runtime_id"] = runtime_id
                if runtime_kind:
                    lease["runtime_kind"] = runtime_kind
    return {
        "worker_runtime_id": runtime_id,
        "worker_runtime_kind": runtime_kind,
        "worker_runtime_reused": runtime_reused,
    }


def _materialize_delegate_entry(
    *,
    task_index: int,
    goal: str,
    parent_agent,
    worker_assignment: Dict[str, Any],
    status: str,
    summary: Optional[str],
    api_calls: int,
    duration: float,
    model: Optional[str],
    exit_reason: str,
    fallback_reason: Optional[str],
    tokens: Dict[str, Any],
    tool_trace: List[Dict[str, Any]],
    capability_snapshot: Optional[Dict[str, Any]],
    context_package: Optional[Dict[str, Any]],
    execution_envelope: Optional[Dict[str, Any]],
    receipt_stem: str,
    execution_path: str = "subagent",
    child_session_id: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    worker_mode = worker_assignment.get("worker_mode") or "cold"
    worker_lease_key = worker_assignment.get("lease_key")
    worker_task_id = worker_assignment.get("task_id") or f"delegate-cold-{uuid.uuid4().hex[:12]}"
    worker_reused = bool(worker_assignment.get("reused"))
    worker_reuse_count = int(worker_assignment.get("reuse_count", 0) or 0)
    worker_ttl_seconds = int(worker_assignment.get("ttl_seconds", 0) or 0)
    worker_lease_age_seconds = float(worker_assignment.get("lease_age_seconds", 0.0) or 0.0)
    worker_runtime = _capture_worker_runtime_metadata(parent_agent, worker_assignment)

    envelope_digest = None
    if execution_envelope:
        envelope_digest = hashlib.sha1(
            json.dumps(execution_envelope, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    execution_receipt = _sanitize_jsonish({
        "task_index": task_index,
        "goal": goal,
        "child_session_id": child_session_id,
        "status": status,
        "summary": summary,
        "api_calls": api_calls,
        "duration_seconds": duration,
        "model": model,
        "execution_path": execution_path,
        "exit_reason": exit_reason,
        "fallback_reason": fallback_reason,
        "tokens": tokens,
        "tool_trace": tool_trace,
        "capability_snapshot": capability_snapshot,
        "context_package": context_package,
        "execution_envelope": execution_envelope,
        "execution_envelope_digest": envelope_digest,
        "worker_mode": worker_mode,
        "worker_lease_key": worker_lease_key,
        "worker_task_id": worker_task_id,
        "worker_reused": worker_reused,
        "worker_reuse_count": worker_reuse_count,
        "worker_runtime_id": worker_runtime.get("worker_runtime_id"),
        "worker_runtime_kind": worker_runtime.get("worker_runtime_kind"),
        "worker_runtime_reused": worker_runtime.get("worker_runtime_reused"),
    }) or {}
    from tools.execution_receipts import persist_execution_receipt

    execution_receipt["receipt_id"] = f"{receipt_stem}-execution-receipt"
    receipt_path = persist_execution_receipt(execution_receipt)

    entry: Dict[str, Any] = {
        "task_index": task_index,
        "status": status,
        "summary": summary,
        "api_calls": api_calls,
        "duration_seconds": duration,
        "model": model,
        "execution_path": execution_path,
        "exit_reason": exit_reason,
        "fallback_reason": fallback_reason,
        "tokens": tokens,
        "tool_trace": tool_trace,
        "capability_snapshot": capability_snapshot,
        "context_package": context_package,
        "execution_envelope": execution_envelope,
        "execution_envelope_digest": envelope_digest,
        "execution_receipt_path": receipt_path,
        "worker_mode": worker_mode,
        "worker_lease_key": worker_lease_key,
        "worker_task_id": worker_task_id,
        "worker_reused": worker_reused,
        "worker_reuse_count": worker_reuse_count,
        "worker_runtime_id": worker_runtime.get("worker_runtime_id"),
        "worker_runtime_kind": worker_runtime.get("worker_runtime_kind"),
        "worker_runtime_reused": worker_runtime.get("worker_runtime_reused"),
        "worker_lease_ttl_seconds": worker_ttl_seconds,
        "worker_lease_age_seconds": worker_lease_age_seconds,
    }
    if error:
        entry["error"] = error
    return entry


def _build_child_progress_callback(task_index: int, parent_agent, task_count: int = 1) -> Optional[callable]:
    """Build a callback that relays child agent tool calls to the parent display.

    Two display paths:
      CLI:     prints tree-view lines above the parent's delegation spinner
      Gateway: batches tool names and relays to parent's progress callback

    Returns None if no display mechanism is available, in which case the
    child agent runs with no progress callback (identical to current behavior).
    """
    spinner = getattr(parent_agent, '_delegate_spinner', None)
    parent_cb = getattr(parent_agent, 'tool_progress_callback', None)

    if not spinner and not parent_cb:
        return None  # No display → no callback → zero behavior change

    # Show 1-indexed prefix only in batch mode (multiple tasks)
    prefix = f"[{task_index + 1}] " if task_count > 1 else ""

    # Gateway: batch tool names, flush periodically
    _BATCH_SIZE = 5
    _batch: List[str] = []

    def _callback(event_type: str, tool_name: str = None, preview: str = None, args=None, **kwargs):
        # event_type is one of: "tool.started", "tool.completed",
        # "reasoning.available", "_thinking", "subagent_progress"

        # "_thinking" / reasoning events
        if event_type in ("_thinking", "reasoning.available"):
            text = preview or tool_name or ""
            if spinner:
                short = (text[:55] + "...") if len(text) > 55 else text
                try:
                    spinner.print_above(f" {prefix}├─ 💭 \"{short}\"")
                except Exception as e:
                    logger.debug("Spinner print_above failed: %s", e)
            # Don't relay thinking to gateway (too noisy for chat)
            return

        # tool.completed — no display needed here (spinner shows on started)
        if event_type == "tool.completed":
            return

        # tool.started — display and batch for parent relay
        if spinner:
            short = (preview[:35] + "...") if preview and len(preview) > 35 else (preview or "")
            from agent.display import get_tool_emoji
            emoji = get_tool_emoji(tool_name or "")
            line = f" {prefix}├─ {emoji} {tool_name}"
            if short:
                line += f"  \"{short}\""
            try:
                spinner.print_above(line)
            except Exception as e:
                logger.debug("Spinner print_above failed: %s", e)

        if parent_cb:
            _batch.append(tool_name or "")
            if len(_batch) >= _BATCH_SIZE:
                summary = ", ".join(_batch)
                try:
                    parent_cb("subagent_progress", f"🔀 {prefix}{summary}")
                except Exception as e:
                    logger.debug("Parent callback failed: %s", e)
                _batch.clear()

    def _flush():
        """Flush remaining batched tool names to gateway on completion."""
        if parent_cb and _batch:
            summary = ", ".join(_batch)
            try:
                parent_cb("subagent_progress", f"🔀 {prefix}{summary}")
            except Exception as e:
                logger.debug("Parent callback flush failed: %s", e)
            _batch.clear()

    _callback._flush = _flush
    return _callback


def _build_child_agent(
    task_index: int,
    goal: str,
    context: Optional[str],
    toolsets: Optional[List[str]],
    model: Optional[str],
    max_iterations: int,
    parent_agent,
    execution_envelope: Optional[Dict[str, Any]] = None,
    context_package: Optional[Dict[str, Any]] = None,
    worker_assignment: Optional[Dict[str, Any]] = None,
    # Credential overrides from delegation config (provider:model resolution)
    override_provider: Optional[str] = None,
    override_base_url: Optional[str] = None,
    override_api_key: Optional[str] = None,
    override_api_mode: Optional[str] = None,
    # ACP transport overrides — lets a non-ACP parent spawn ACP child agents
    override_acp_command: Optional[str] = None,
    override_acp_args: Optional[List[str]] = None,
):
    """
    Build a child AIAgent on the main thread (thread-safe construction).
    Returns the constructed child agent without running it.

    When override_* params are set (from delegation config), the child uses
    those credentials instead of inheriting from the parent.  This enables
    routing subagents to a different provider:model pair (e.g. cheap/fast
    model on OpenRouter while the parent runs on Nous Portal).
    """
    from run_agent import AIAgent

    requested_toolsets = list(toolsets or [])
    child_toolsets = _resolve_child_toolsets(parent_agent, toolsets)

    direct_work_order, direct_work_order_error = _resolve_direct_terminal_work_order(
        execution_envelope,
        {"effective_toolsets": child_toolsets},
    )
    workspace_hint = None if (direct_work_order is not None or direct_work_order_error is not None) else _resolve_workspace_hint(parent_agent)

    # Extract parent's API key so subagents inherit auth (e.g. Nous Portal).
    parent_api_key = getattr(parent_agent, "api_key", None)
    if (not parent_api_key) and hasattr(parent_agent, "_client_kwargs"):
        parent_api_key = parent_agent._client_kwargs.get("api_key")

    # Build progress callback to relay tool calls to parent display
    child_progress_cb = _build_child_progress_callback(task_index, parent_agent)

    # Each subagent gets its own iteration budget capped at max_iterations
    # (configurable via delegation.max_iterations, default 50).  This means
    # total iterations across parent + subagents can exceed the parent's
    # max_iterations.  The user controls the per-subagent cap in config.yaml.

    child_thinking_cb = None
    if child_progress_cb:
        def _child_thinking(text: str) -> None:
            if not text:
                return
            try:
                child_progress_cb("_thinking", text)
            except Exception as e:
                logger.debug("Child thinking callback relay failed: %s", e)

        child_thinking_cb = _child_thinking

    # Resolve effective credentials: config override > parent inherit
    effective_model = model or parent_agent.model
    effective_provider = override_provider or getattr(parent_agent, "provider", None)
    effective_base_url = override_base_url or parent_agent.base_url
    effective_api_key = override_api_key or parent_api_key
    effective_api_mode = override_api_mode or getattr(parent_agent, "api_mode", None)
    effective_acp_command = override_acp_command or getattr(parent_agent, "acp_command", None)
    effective_acp_args = list(override_acp_args if override_acp_args is not None else (getattr(parent_agent, "acp_args", []) or []))

    # Resolve reasoning config: delegation override > parent inherit
    parent_reasoning = getattr(parent_agent, "reasoning_config", None)
    child_reasoning = parent_reasoning
    try:
        delegation_cfg = _load_config()
        delegation_effort = str(delegation_cfg.get("reasoning_effort") or "").strip()
        if delegation_effort:
            from hermes_constants import parse_reasoning_effort
            parsed = parse_reasoning_effort(delegation_effort)
            if parsed is not None:
                child_reasoning = parsed
            else:
                logger.warning(
                    "Unknown delegation.reasoning_effort '%s', inheriting parent level",
                    delegation_effort,
                )
    except Exception as exc:
        logger.debug("Could not load delegation reasoning_effort: %s", exc)

    capability_snapshot = {
        "requested_toolsets": requested_toolsets,
        "effective_toolsets": list(child_toolsets),
        "blocked_tools": sorted(DELEGATE_BLOCKED_TOOLS),
        "provider": effective_provider,
        "model": effective_model,
        "acp_command": effective_acp_command,
    }
    effective_context_package = _build_context_package(
        goal=goal,
        context=context,
        parent_agent=parent_agent,
        workspace_path=workspace_hint,
        requested_toolsets=requested_toolsets,
        effective_toolsets=child_toolsets,
        context_package=context_package,
    )
    effective_execution_envelope = _build_execution_envelope(
        goal=goal,
        capability_snapshot=capability_snapshot,
        context_package=effective_context_package,
        execution_envelope=execution_envelope,
    )
    child_prompt = _build_child_system_prompt(
        goal,
        context,
        workspace_path=workspace_hint,
        execution_envelope=effective_execution_envelope,
        context_package=effective_context_package,
    )

    child = AIAgent(
        base_url=effective_base_url,
        api_key=effective_api_key,
        model=effective_model,
        provider=effective_provider,
        api_mode=effective_api_mode,
        acp_command=effective_acp_command,
        acp_args=effective_acp_args,
        max_iterations=max_iterations,
        max_tokens=getattr(parent_agent, "max_tokens", None),
        reasoning_config=child_reasoning,
        prefill_messages=getattr(parent_agent, "prefill_messages", None),
        enabled_toolsets=child_toolsets,
        quiet_mode=True,
        ephemeral_system_prompt=child_prompt,
        log_prefix=f"[subagent-{task_index}]",
        platform=parent_agent.platform,
        skip_context_files=True,
        skip_memory=True,
        clarify_callback=None,
        thinking_callback=child_thinking_cb,
        session_db=getattr(parent_agent, '_session_db', None),
        parent_session_id=getattr(parent_agent, 'session_id', None),
        providers_allowed=parent_agent.providers_allowed,
        providers_ignored=parent_agent.providers_ignored,
        providers_order=parent_agent.providers_order,
        provider_sort=parent_agent.provider_sort,
        tool_progress_callback=child_progress_cb,
        iteration_budget=None,  # fresh budget per subagent
    )
    child._print_fn = getattr(parent_agent, '_print_fn', None)
    # Set delegation depth so children can't spawn grandchildren
    child._delegate_depth = getattr(parent_agent, '_delegate_depth', 0) + 1
    child._delegate_capability_snapshot = capability_snapshot
    child._delegate_context_package = effective_context_package
    child._delegate_execution_envelope = effective_execution_envelope
    child._delegate_worker_assignment = _sanitize_jsonish(worker_assignment) or None

    # Share a credential pool with the child when possible so subagents can
    # rotate credentials on rate limits instead of getting pinned to one key.
    child_pool = _resolve_child_credential_pool(effective_provider, parent_agent)
    if child_pool is not None:
        child._credential_pool = child_pool

    # Register child for interrupt propagation
    if hasattr(parent_agent, '_active_children'):
        lock = getattr(parent_agent, '_active_children_lock', None)
        if lock:
            with lock:
                parent_agent._active_children.append(child)
        else:
            parent_agent._active_children.append(child)

    return child

def _run_single_child(
    task_index: int,
    goal: str,
    child=None,
    parent_agent=None,
    **_kwargs,
) -> Dict[str, Any]:
    """
    Run a pre-built child agent. Called from within a thread.
    Returns a structured result dict.
    """
    child_start = time.monotonic()

    # Get the progress callback from the child agent
    child_progress_cb = getattr(child, 'tool_progress_callback', None)

    # Restore parent tool names using the value saved before child construction
    # mutated the global. This is the correct parent toolset, not the child's.
    import model_tools
    _saved_tool_names = getattr(child, "_delegate_saved_tool_names",
                                list(model_tools._last_resolved_tool_names))

    worker_assignment = _sanitize_jsonish(getattr(child, '_delegate_worker_assignment', None)) or {}
    worker_task_id = worker_assignment.get("task_id") or f"delegate-cold-{uuid.uuid4().hex[:12]}"
    worker_keep_warm = bool(worker_assignment.get("keep_warm"))
    capability_snapshot = _sanitize_jsonish(getattr(child, "_delegate_capability_snapshot", None))
    context_package = _sanitize_jsonish(getattr(child, "_delegate_context_package", None))
    execution_envelope = _sanitize_jsonish(getattr(child, "_delegate_execution_envelope", None))
    direct_work_order, direct_work_order_error = _resolve_direct_terminal_work_order(execution_envelope, capability_snapshot)

    child_pool = getattr(child, '_credential_pool', None)
    leased_cred_id = None
    if child_pool is not None and direct_work_order is None and direct_work_order_error is None:
        leased_cred_id = child_pool.acquire_lease()
        if leased_cred_id is not None:
            try:
                leased_entry = child_pool.current()
                if leased_entry is not None and hasattr(child, '_swap_credential'):
                    child._swap_credential(leased_entry)
            except Exception as exc:
                logger.debug("Failed to bind child to leased credential: %s", exc)

    # Heartbeat: periodically propagate child activity to the parent so the
    # gateway inactivity timeout doesn't fire while the subagent is working.
    # Without this, the parent's _last_activity_ts freezes when delegate_task
    # starts and the gateway eventually kills the agent for "no activity".
    _heartbeat_stop = threading.Event()

    def _heartbeat_loop():
        while not _heartbeat_stop.wait(_HEARTBEAT_INTERVAL):
            if parent_agent is None:
                continue
            touch = getattr(parent_agent, '_touch_activity', None)
            if not touch:
                continue
            desc = f"delegate_task: subagent {task_index} working"
            try:
                if direct_work_order is not None:
                    desc = f"delegate_task: direct terminal work-order running (task {task_index})"
                else:
                    child_summary = child.get_activity_summary()
                    child_tool = child_summary.get("current_tool")
                    child_iter = child_summary.get("api_call_count", 0)
                    child_max = child_summary.get("max_iterations", 0)
                    if child_tool:
                        desc = (f"delegate_task: subagent running {child_tool} "
                                f"(iteration {child_iter}/{child_max})")
                    else:
                        child_desc = child_summary.get("last_activity_desc", "")
                        if child_desc:
                            desc = (f"delegate_task: subagent {child_desc} "
                                    f"(iteration {child_iter}/{child_max})")
            except Exception:
                pass
            try:
                touch(desc)
            except Exception:
                pass

    _heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    _heartbeat_thread.start()

    try:
        try:
            from tools.file_tools import clear_read_tracker
            clear_read_tracker(worker_task_id)
        except Exception:
            pass

        if direct_work_order_error is not None:
            duration = round(time.monotonic() - child_start, 2)
            direct_receipt_stem = f"delegate-direct-{task_index}-{uuid.uuid4().hex[:8]}"
            return _materialize_delegate_entry(
                task_index=task_index,
                goal=goal,
                parent_agent=parent_agent,
                worker_assignment=worker_assignment,
                status="failed",
                summary=None,
                api_calls=0,
                duration=duration,
                model=None,
                exit_reason="invalid_direct_terminal_work_order",
                fallback_reason="invalid_direct_terminal_work_order",
                tokens={"input": 0, "output": 0},
                tool_trace=[],
                capability_snapshot=capability_snapshot,
                context_package=context_package,
                execution_envelope=execution_envelope,
                receipt_stem=direct_receipt_stem,
                execution_path="direct_terminal_work_order",
                child_session_id=None,
                error=direct_work_order_error,
            )

        if direct_work_order is not None:
            from tools.terminal_tool import terminal_tool

            terminal_raw = terminal_tool(
                command=direct_work_order["command"],
                timeout=direct_work_order.get("timeout_seconds"),
                task_id=worker_task_id,
                workdir=direct_work_order.get("workdir"),
            )
            terminal_result = json.loads(terminal_raw)
            duration = round(time.monotonic() - child_start, 2)
            summary = str(terminal_result.get("output") or "").strip() or None
            exit_code = terminal_result.get("exit_code")
            if isinstance(exit_code, bool):
                exit_code = int(exit_code)
            if not isinstance(exit_code, int):
                exit_code = 0
            tool_status = _classify_tool_message_status(terminal_raw)
            exit_reason = "completed" if exit_code == 0 else f"terminal_exit_code_{exit_code}"
            fallback_reason = None if exit_reason == "completed" else exit_reason
            status = "completed" if exit_code == 0 and summary else "failed"
            return _materialize_delegate_entry(
                task_index=task_index,
                goal=goal,
                parent_agent=parent_agent,
                worker_assignment=worker_assignment,
                status=status,
                summary=summary,
                api_calls=0,
                duration=duration,
                model=None,
                exit_reason=exit_reason,
                fallback_reason=fallback_reason,
                tokens={"input": 0, "output": 0},
                tool_trace=[{
                    "tool": "terminal",
                    "args_bytes": len(direct_work_order["command"]),
                    "result_bytes": len(terminal_raw),
                    "status": tool_status,
                }],
                capability_snapshot=capability_snapshot,
                context_package=context_package,
                execution_envelope=execution_envelope,
                receipt_stem=f"delegate-direct-{task_index}-{int(child_start)}",
                execution_path="direct_terminal_work_order",
                child_session_id=None,
                error=str(terminal_result.get("error") or "") or None,
            )

        result = child.run_conversation(user_message=goal, task_id=worker_task_id)

        if child_progress_cb and hasattr(child_progress_cb, '_flush'):
            try:
                child_progress_cb._flush()
            except Exception as e:
                logger.debug("Progress callback flush failed: %s", e)

        duration = round(time.monotonic() - child_start, 2)
        summary = result.get("final_response") or ""
        completed = result.get("completed", False)
        interrupted = result.get("interrupted", False)
        api_calls = result.get("api_calls", 0)

        if interrupted:
            status = "interrupted"
        elif summary:
            status = "completed"
        else:
            status = "failed"

        tool_trace: list[Dict[str, Any]] = []
        trace_by_id: Dict[str, Dict[str, Any]] = {}
        messages = result.get("messages") or []
        if isinstance(messages, list):
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                if msg.get("role") == "assistant":
                    for tc in (msg.get("tool_calls") or []):
                        fn = tc.get("function", {})
                        entry_t = {
                            "tool": fn.get("name", "unknown"),
                            "args_bytes": len(fn.get("arguments", "")),
                        }
                        tool_trace.append(entry_t)
                        tc_id = tc.get("id")
                        if tc_id:
                            trace_by_id[tc_id] = entry_t
                elif msg.get("role") == "tool":
                    content = msg.get("content", "")
                    result_meta = {
                        "result_bytes": len(content),
                        "status": _classify_tool_message_status(content),
                    }
                    tc_id = msg.get("tool_call_id")
                    target = trace_by_id.get(tc_id) if tc_id else None
                    if target is not None:
                        target.update(result_meta)
                    elif tool_trace:
                        tool_trace[-1].update(result_meta)

        if interrupted:
            exit_reason = "interrupted"
        elif completed:
            exit_reason = "completed"
        else:
            exit_reason = "max_iterations"

        _input_tokens = getattr(child, "session_prompt_tokens", 0)
        _output_tokens = getattr(child, "session_completion_tokens", 0)
        _model = getattr(child, "model", None)
        fallback_reason = None if exit_reason == "completed" else exit_reason
        return _materialize_delegate_entry(
            task_index=task_index,
            goal=goal,
            parent_agent=parent_agent,
            worker_assignment=worker_assignment,
            status=status,
            summary=summary,
            api_calls=api_calls,
            duration=duration,
            model=_model if isinstance(_model, str) else None,
            exit_reason=exit_reason,
            fallback_reason=fallback_reason,
            tokens={
                "input": _input_tokens if isinstance(_input_tokens, (int, float)) else 0,
                "output": _output_tokens if isinstance(_output_tokens, (int, float)) else 0,
            },
            tool_trace=tool_trace,
            capability_snapshot=capability_snapshot,
            context_package=context_package,
            execution_envelope=execution_envelope,
            receipt_stem=getattr(child, "session_id", None) or f"delegate-{task_index}-{int(child_start)}",
            execution_path="subagent",
            child_session_id=getattr(child, "session_id", None),
            error=result.get("error", "Subagent did not produce a response.") if status == "failed" else None,
        )

    except Exception as exc:
        duration = round(time.monotonic() - child_start, 2)
        logging.exception(f"[subagent-{task_index}] failed")
        return {
            "task_index": task_index,
            "status": "error",
            "summary": None,
            "error": str(exc),
            "api_calls": 0,
            "duration_seconds": duration,
        }

    finally:
        # Stop the heartbeat thread so it doesn't keep touching parent activity
        # after the child has finished (or failed).
        _heartbeat_stop.set()
        _heartbeat_thread.join(timeout=5)

        try:
            from tools.file_tools import clear_read_tracker
            clear_read_tracker(worker_task_id)
        except Exception:
            pass

        if not worker_keep_warm:
            try:
                from tools.terminal_tool import cleanup_vm
                cleanup_vm(worker_task_id)
            except Exception:
                logger.debug("Failed to cleanup cold worker task %s", worker_task_id)

        if child_pool is not None and leased_cred_id is not None:
            try:
                child_pool.release_lease(leased_cred_id)
            except Exception as exc:
                logger.debug("Failed to release credential lease: %s", exc)

        # Restore the parent's tool names so the process-global is correct
        # for any subsequent execute_code calls or other consumers.
        import model_tools

        saved_tool_names = getattr(child, "_delegate_saved_tool_names", None)
        if isinstance(saved_tool_names, list):
            model_tools._last_resolved_tool_names = list(saved_tool_names)

        # Remove child from active tracking

        # Unregister child from interrupt propagation
        if hasattr(parent_agent, '_active_children'):
            try:
                lock = getattr(parent_agent, '_active_children_lock', None)
                if lock:
                    with lock:
                        parent_agent._active_children.remove(child)
                else:
                    parent_agent._active_children.remove(child)
            except (ValueError, UnboundLocalError) as e:
                logger.debug("Could not remove child from active_children: %s", e)

        # Close tool resources (terminal sandboxes, browser daemons,
        # background processes, httpx clients) so subagent subprocesses
        # don't outlive the delegation.
        try:
            if hasattr(child, 'close'):
                child.close()
        except Exception:
            logger.debug("Failed to close child agent after delegation")

def delegate_task(
    goal: Optional[str] = None,
    context: Optional[str] = None,
    toolsets: Optional[List[str]] = None,
    tasks: Optional[List[Dict[str, Any]]] = None,
    max_iterations: Optional[int] = None,
    execution_envelope: Optional[Dict[str, Any]] = None,
    context_package: Optional[Dict[str, Any]] = None,
    acp_command: Optional[str] = None,
    acp_args: Optional[List[str]] = None,
    parent_agent=None,
) -> str:
    """
    Spawn one or more child agents to handle delegated tasks.

    Supports two modes:
      - Single: provide goal (+ optional context, toolsets)
      - Batch:  provide tasks array [{goal, context, toolsets}, ...]

    Returns JSON with results array, one entry per task.
    """
    if parent_agent is None:
        return tool_error("delegate_task requires a parent agent context.")

    # Depth limit
    depth = getattr(parent_agent, '_delegate_depth', 0)
    if depth >= MAX_DEPTH:
        return json.dumps({
            "error": (
                f"Delegation depth limit reached ({MAX_DEPTH}). "
                "Subagents cannot spawn further subagents."
            )
        })

    # Load config
    cfg = _load_config()
    default_max_iter = cfg.get("max_iterations", DEFAULT_MAX_ITERATIONS)
    effective_max_iter = max_iterations or default_max_iter

    # Resolve delegation credentials (provider:model pair).
    # When delegation.provider is configured, this resolves the full credential
    # bundle (base_url, api_key, api_mode) via the same runtime provider system
    # used by CLI/gateway startup.  When unconfigured, returns None values so
    # children inherit from the parent.
    try:
        creds = _resolve_delegation_credentials(cfg, parent_agent)
    except ValueError as exc:
        return tool_error(str(exc))

    # Normalize to task list
    max_children = _get_max_concurrent_children()
    if tasks and isinstance(tasks, list):
        if len(tasks) > max_children:
            return tool_error(
                f"Too many tasks: {len(tasks)} provided, but "
                f"max_concurrent_children is {max_children}. "
                f"Either reduce the task count, split into multiple "
                f"delegate_task calls, or increase "
                f"delegation.max_concurrent_children in config.yaml."
            )
        task_list = tasks
    elif goal and isinstance(goal, str) and goal.strip():
        task_list = [{
            "goal": goal,
            "context": context,
            "toolsets": toolsets,
            "execution_envelope": execution_envelope,
            "context_package": context_package,
        }]
    else:
        return tool_error("Provide either 'goal' (single task) or 'tasks' (batch).")

    if not task_list:
        return tool_error("No tasks provided.")

    # Validate each task has a goal
    for i, task in enumerate(task_list):
        if not task.get("goal", "").strip():
            return tool_error(f"Task {i} is missing a 'goal'.")

    overall_start = time.monotonic()
    results = []

    n_tasks = len(task_list)
    # Track goal labels for progress display (truncated for readability)
    task_labels = [t["goal"][:40] for t in task_list]

    # Save parent tool names BEFORE any child construction mutates the global.
    # _build_child_agent() calls AIAgent() which calls get_tool_definitions(),
    # which overwrites model_tools._last_resolved_tool_names with child's toolset.
    import model_tools as _model_tools
    _parent_tool_names = list(_model_tools._last_resolved_tool_names)

    # Build all child agents on the main thread (thread-safe construction)
    # Wrapped in try/finally so the global is always restored even if a
    # child build raises (otherwise _last_resolved_tool_names stays corrupted).
    children = []
    try:
        for i, t in enumerate(task_list):
            requested_toolsets = t.get("toolsets") or toolsets
            effective_child_toolsets = _resolve_child_toolsets(parent_agent, requested_toolsets)
            maybe_direct_work_order, maybe_direct_work_order_error = _resolve_direct_terminal_work_order(
                t.get("execution_envelope") or execution_envelope,
                {"effective_toolsets": effective_child_toolsets},
            )
            effective_workspace_hint = None if (maybe_direct_work_order is not None or maybe_direct_work_order_error is not None) else _resolve_workspace_hint(parent_agent)
            effective_model = creds["model"] or getattr(parent_agent, "model", None)
            effective_provider = creds["provider"] or getattr(parent_agent, "provider", None)
            effective_base_url = creds["base_url"] or getattr(parent_agent, "base_url", None)
            effective_api_mode = creds["api_mode"] or getattr(parent_agent, "api_mode", None)
            worker_assignment = _build_delegate_worker_assignment(
                parent_agent,
                cfg=cfg,
                task_count=n_tasks,
                toolsets=effective_child_toolsets,
                model=effective_model,
                provider=effective_provider,
                base_url=effective_base_url,
                api_mode=effective_api_mode,
                workspace_path=effective_workspace_hint,
            )
            child = _build_child_agent(
                task_index=i, goal=t["goal"], context=t.get("context"),
                toolsets=requested_toolsets, model=creds["model"],
                max_iterations=effective_max_iter, parent_agent=parent_agent,
                execution_envelope=t.get("execution_envelope") or execution_envelope,
                context_package=t.get("context_package") or context_package,
                worker_assignment=worker_assignment,
                override_provider=creds["provider"], override_base_url=creds["base_url"],
                override_api_key=creds["api_key"],
                override_api_mode=creds["api_mode"],
                override_acp_command=t.get("acp_command") or acp_command,
                override_acp_args=t.get("acp_args") or acp_args,
            )
            # Override with correct parent tool names (before child construction mutated global)
            child._delegate_saved_tool_names = _parent_tool_names
            children.append((i, t, child))
    finally:
        # Authoritative restore: reset global to parent's tool names after all children built
        _model_tools._last_resolved_tool_names = _parent_tool_names

    if n_tasks == 1:
        # Single task -- run directly (no thread pool overhead)
        _i, _t, child = children[0]
        result = _run_single_child(0, _t["goal"], child, parent_agent)
        results.append(result)
    else:
        # Batch -- run in parallel with per-task progress lines
        completed_count = 0
        spinner_ref = getattr(parent_agent, '_delegate_spinner', None)

        with ThreadPoolExecutor(max_workers=max_children) as executor:
            futures = {}
            for i, t, child in children:
                future = executor.submit(
                    _run_single_child,
                    task_index=i,
                    goal=t["goal"],
                    child=child,
                    parent_agent=parent_agent,
                )
                futures[future] = i

            for future in as_completed(futures):
                try:
                    entry = future.result()
                except Exception as exc:
                    idx = futures[future]
                    entry = {
                        "task_index": idx,
                        "status": "error",
                        "summary": None,
                        "error": str(exc),
                        "api_calls": 0,
                        "duration_seconds": 0,
                    }
                results.append(entry)
                completed_count += 1

                # Print per-task completion line above the spinner
                idx = entry["task_index"]
                label = task_labels[idx] if idx < len(task_labels) else f"Task {idx}"
                dur = entry.get("duration_seconds", 0)
                status = entry.get("status", "?")
                icon = "✓" if status == "completed" else "✗"
                remaining = n_tasks - completed_count
                completion_line = f"{icon} [{idx+1}/{n_tasks}] {label}  ({dur}s)"
                if spinner_ref:
                    try:
                        spinner_ref.print_above(completion_line)
                    except Exception:
                        print(f"  {completion_line}")
                else:
                    print(f"  {completion_line}")

                # Update spinner text to show remaining count
                if spinner_ref and remaining > 0:
                    try:
                        spinner_ref.update_text(f"🔀 {remaining} task{'s' if remaining != 1 else ''} remaining")
                    except Exception as e:
                        logger.debug("Spinner update_text failed: %s", e)

        # Sort by task_index so results match input order
        results.sort(key=lambda r: r["task_index"])

    # Notify parent's memory provider of delegation outcomes
    if parent_agent and hasattr(parent_agent, '_memory_manager') and parent_agent._memory_manager:
        for entry in results:
            try:
                _task_goal = task_list[entry["task_index"]]["goal"] if entry["task_index"] < len(task_list) else ""
                parent_agent._memory_manager.on_delegation(
                    task=_task_goal,
                    result=entry.get("summary", "") or "",
                    child_session_id=(
                        ""
                        if entry.get("execution_path") == "direct_terminal_work_order"
                        else getattr(children[entry["task_index"]][2], "session_id", "") if entry["task_index"] < len(children) else ""
                    ),
                )
            except Exception:
                pass

    total_duration = round(time.monotonic() - overall_start, 2)

    return json.dumps({
        "results": results,
        "total_duration_seconds": total_duration,
    }, ensure_ascii=False)


def _resolve_child_credential_pool(effective_provider: Optional[str], parent_agent):
    """Resolve a credential pool for the child agent.

    Rules:
    1. Same provider as the parent -> share the parent's pool so cooldown state
       and rotation stay synchronized.
    2. Different provider -> try to load that provider's own pool.
    3. No pool available -> return None and let the child keep the inherited
       fixed credential behavior.
    """
    if not effective_provider:
        return getattr(parent_agent, "_credential_pool", None)

    parent_provider = getattr(parent_agent, "provider", None) or ""
    parent_pool = getattr(parent_agent, "_credential_pool", None)
    if parent_pool is not None and effective_provider == parent_provider:
        return parent_pool

    try:
        from agent.credential_pool import load_pool
        pool = load_pool(effective_provider)
        if pool is not None and pool.has_credentials():
            return pool
    except Exception as exc:
        logger.debug(
            "Could not load credential pool for child provider '%s': %s",
            effective_provider,
            exc,
        )
    return None


def _resolve_delegation_credentials(cfg: dict, parent_agent) -> dict:
    """Resolve credentials for subagent delegation.

    If ``delegation.base_url`` is configured, subagents use that direct
    OpenAI-compatible endpoint. Otherwise, if ``delegation.provider`` is
    configured, the full credential bundle (base_url, api_key, api_mode,
    provider) is resolved via the runtime provider system — the same path used
    by CLI/gateway startup. This lets subagents run on a completely different
    provider:model pair.

    If neither base_url nor provider is configured, returns None values so the
    child inherits everything from the parent agent.

    Raises ValueError with a user-friendly message on credential failure.
    """
    configured_model = str(cfg.get("model") or "").strip() or None
    configured_provider = str(cfg.get("provider") or "").strip() or None
    configured_base_url = str(cfg.get("base_url") or "").strip() or None
    configured_api_key = str(cfg.get("api_key") or "").strip() or None

    if configured_base_url:
        api_key = (
            configured_api_key
            or os.getenv("OPENAI_API_KEY", "").strip()
        )
        if not api_key:
            raise ValueError(
                "Delegation base_url is configured but no API key was found. "
                "Set delegation.api_key or OPENAI_API_KEY."
            )

        base_lower = configured_base_url.lower()
        provider = "custom"
        api_mode = "chat_completions"
        if "chatgpt.com/backend-api/codex" in base_lower:
            provider = "openai-codex"
            api_mode = "codex_responses"
        elif "api.anthropic.com" in base_lower:
            provider = "anthropic"
            api_mode = "anthropic_messages"

        return {
            "model": configured_model,
            "provider": provider,
            "base_url": configured_base_url,
            "api_key": api_key,
            "api_mode": api_mode,
        }

    if not configured_provider:
        # No provider override — child inherits everything from parent
        return {
            "model": configured_model,
            "provider": None,
            "base_url": None,
            "api_key": None,
            "api_mode": None,
        }

    # Provider is configured — resolve full credentials
    try:
        from hermes_cli.runtime_provider import resolve_runtime_provider
        runtime = resolve_runtime_provider(requested=configured_provider)
    except Exception as exc:
        raise ValueError(
            f"Cannot resolve delegation provider '{configured_provider}': {exc}. "
            f"Check that the provider is configured (API key set, valid provider name), "
            f"or set delegation.base_url/delegation.api_key for a direct endpoint. "
            f"Available providers: openrouter, nous, zai, kimi-coding, minimax."
        ) from exc

    api_key = runtime.get("api_key", "")
    if not api_key:
        raise ValueError(
            f"Delegation provider '{configured_provider}' resolved but has no API key. "
            f"Set the appropriate environment variable or run 'hermes auth'."
        )

    return {
        "model": configured_model,
        "provider": runtime.get("provider"),
        "base_url": runtime.get("base_url"),
        "api_key": api_key,
        "api_mode": runtime.get("api_mode"),
        "command": runtime.get("command"),
        "args": list(runtime.get("args") or []),
    }


def _load_config() -> dict:
    """Load delegation config without importing side-effectful CLI bootstrap.

    If the interactive CLI module is already loaded, reuse its in-memory
    ``CLI_CONFIG`` snapshot. But never import ``cli`` here: importing cli.py
    triggers terminal config -> env bridging, which can silently stomp live
    ``TERMINAL_*`` values mid-delegation and flip the active backend.

    When CLI_CONFIG is unavailable, fall back to the persistent config loader.
    """
    try:
        cli_module = sys.modules.get("cli")
        cli_config = getattr(cli_module, "CLI_CONFIG", None) if cli_module is not None else None
        if isinstance(cli_config, dict):
            cfg = cli_config.get("delegation", {})
            if isinstance(cfg, dict) and cfg:
                return cfg
    except Exception:
        pass
    try:
        from hermes_cli.config import load_config
        full = load_config()
        cfg = full.get("delegation", {})
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# OpenAI Function-Calling Schema
# ---------------------------------------------------------------------------

DELEGATE_TASK_SCHEMA = {
    "name": "delegate_task",
    "description": (
        "Spawn one or more subagents to work on tasks in isolated contexts. "
        "Each subagent gets its own conversation, terminal session, and toolset. "
        "Only the final summary is returned -- intermediate tool results "
        "never enter your context window.\n\n"
        "TWO MODES (one of 'goal' or 'tasks' is required):\n"
        "1. Single task: provide 'goal' (+ optional context, toolsets)\n"
        "2. Batch (parallel): provide 'tasks' array with up to 3 items. "
        "All run concurrently and results are returned together.\n\n"
        "WHEN TO USE delegate_task:\n"
        "- Reasoning-heavy subtasks (debugging, code review, research synthesis)\n"
        "- Tasks that would flood your context with intermediate data\n"
        "- Parallel independent workstreams (research A and B simultaneously)\n\n"
        "WHEN NOT TO USE (use these instead):\n"
        "- Mechanical multi-step work with no reasoning needed -> use execute_code\n"
        "- Single tool call -> just call the tool directly\n"
        "- Tasks needing user interaction -> subagents cannot use clarify\n\n"
        "IMPORTANT:\n"
        "- Subagents have NO memory of your conversation. Pass all relevant "
        "info (file paths, error messages, constraints) via the 'context' field.\n"
        "- Subagents CANNOT call: delegate_task, clarify, memory, send_message, "
        "execute_code.\n"
        "- Each subagent gets its own terminal session (separate working directory and state).\n"
        "- Results are always returned as an array, one entry per task."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": (
                    "What the subagent should accomplish. Be specific and "
                    "self-contained -- the subagent knows nothing about your "
                    "conversation history."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Background information the subagent needs: file paths, "
                    "error messages, project structure, constraints. The more "
                    "specific you are, the better the subagent performs."
                ),
            },
            "toolsets": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Toolsets to enable for this subagent. "
                    "Default: inherits your enabled toolsets. "
                    f"Available toolsets: {_TOOLSET_LIST_STR}. "
                    "Common patterns: ['terminal', 'file'] for code work, "
                    "['web'] for research, ['browser'] for web interaction, "
                    "['terminal', 'file', 'web'] for full-stack tasks."
                ),
            },
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string", "description": "Task goal"},
                        "context": {"type": "string", "description": "Task-specific context"},
                        "toolsets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": f"Toolsets for this specific task. Available: {_TOOLSET_LIST_STR}. Use 'web' for network access, 'terminal' for shell, 'browser' for web interaction.",
                        },
                        "execution_envelope": {
                            "type": "object",
                            "additionalProperties": True,
                            "description": "Optional structured execution contract: task_spec, completion_criteria, artifact_schema, or other task-specific constraints.",
                        },
                        "context_package": {
                            "type": "object",
                            "additionalProperties": True,
                            "description": "Optional structured context package passed alongside the free-form context string.",
                        },
                        "acp_command": {
                            "type": "string",
                            "description": "Per-task ACP command override (e.g. 'claude'). Overrides the top-level acp_command for this task only.",
                        },
                        "acp_args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Per-task ACP args override.",
                        },
                    },
                    "required": ["goal"],
                },
                # No maxItems — the runtime limit is configurable via
                # delegation.max_concurrent_children (default 3) and
                # enforced with a clear error in delegate_task().
                "description": (
                    "Batch mode: tasks to run in parallel (limit configurable via delegation.max_concurrent_children, default 3). Each gets "
                    "its own subagent with isolated context and terminal session. "
                    "When provided, top-level goal/context/toolsets are ignored."
                ),
            },
            "max_iterations": {
                "type": "integer",
                "description": (
                    "Max tool-calling turns per subagent (default: 50). "
                    "Only set lower for simple tasks."
                ),
            },
            "execution_envelope": {
                "type": "object",
                "additionalProperties": True,
                "description": "Optional structured execution contract: task_spec, completion_criteria, artifact_schema, or other task-level constraints.",
            },
            "context_package": {
                "type": "object",
                "additionalProperties": True,
                "description": "Optional structured context package passed alongside the free-form context string.",
            },
            "acp_command": {
                "type": "string",
                "description": (
                    "Override ACP command for child agents (e.g. 'claude', 'copilot'). "
                    "When set, children use ACP subprocess transport instead of inheriting "
                    "the parent's transport. Enables spawning Claude Code (claude --acp --stdio) "
                    "or other ACP-capable agents from any parent, including Discord/Telegram/CLI."
                ),
            },
            "acp_args": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Arguments for the ACP command (default: ['--acp', '--stdio']). "
                    "Only used when acp_command is set. Example: ['--acp', '--stdio', '--model', 'claude-opus-4-6']"
                ),
            },
        },
        "required": [],
    },
}


# --- Registry ---
from tools.registry import registry, tool_error

registry.register(
    name="delegate_task",
    toolset="delegation",
    schema=DELEGATE_TASK_SCHEMA,
    handler=lambda args, **kw: delegate_task(
        goal=args.get("goal"),
        context=args.get("context"),
        toolsets=args.get("toolsets"),
        tasks=args.get("tasks"),
        max_iterations=args.get("max_iterations"),
        execution_envelope=args.get("execution_envelope"),
        context_package=args.get("context_package"),
        acp_command=args.get("acp_command"),
        acp_args=args.get("acp_args"),
        parent_agent=kw.get("parent_agent")),
    check_fn=check_delegate_requirements,
    emoji="🔀",
)
