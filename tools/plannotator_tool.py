"""Native Plannotator session launcher.

This tool wraps operator-configured launch commands so Hermes can open
Plannotator review/annotation sessions without relying on skills alone.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tools.exposure_helpers import run_command_template
from tools.registry import registry

logger = logging.getLogger(__name__)

_DEFAULT_TEMPLATES = {
    "prepare": "python3 ~/services/plannotator-bridge/start_session.py prepare",
    "review": "python3 ~/services/plannotator-bridge/start_session.py review{review_target_arg}",
    "annotate": "python3 ~/services/plannotator-bridge/start_session.py annotate {artifact_path}",
    "last": "python3 ~/services/plannotator-bridge/start_session.py last",
}

_ENV_TEMPLATE_BY_ACTION = {
    "prepare": "HERMES_PLANNOTATOR_PREPARE_TEMPLATE",
    "review": "HERMES_PLANNOTATOR_REVIEW_TEMPLATE",
    "annotate": "HERMES_PLANNOTATOR_ANNOTATE_TEMPLATE",
    "last": "HERMES_PLANNOTATOR_LAST_TEMPLATE",
}

_DEFAULT_LAUNCH_TIMEOUT_SECONDS = 120
_DEFAULT_COMPLETION_TIMEOUT_SECONDS = 3600
_DEFAULT_POLL_INTERVAL_SECONDS = 2.0
_MAX_LOG_BYTES = 128_000
_PLANNOTATOR_HOST_ENV = "PLANNOTATOR_HOST"

_PLANNOTATOR_SCHEMA = {
    "name": "plannotator_session",
    "description": (
        "Launch or prepare a Plannotator review/annotation session using operator-configured command templates. "
        "By default review/annotate waits synchronously for the session to finish or timeout and returns final log output. "
        "For inline UX: first call action='prepare' to reserve a URL/host, then send that URL with send_message, then call "
        "action='review' or action='annotate' with fixed_host set to the prepared host so Plannotator uses the same URL while Hermes waits."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["prepare", "review", "annotate", "last"],
                "description": "prepare: reserve/generate a Plannotator host+URL before launching. review: current diff or PR/MR URL. annotate: markdown artifact path. last: last-message flow if the launcher supports it."
            },
            "review_target": {
                "type": "string",
                "description": "Optional PR/MR URL or other review target for action='review'. Omit to review the current local diff."
            },
            "artifact_path": {
                "type": "string",
                "description": "Absolute path to a markdown artifact when action='annotate'."
            },
            "repo_path": {
                "type": "string",
                "description": "Optional working directory for review launches against the current local diff."
            },
            "fixed_host": {
                "type": "string",
                "description": "Optional fixed host to use for prepare/review/annotate, e.g. 'plannotator-abc123.a.cloud77.it'. Use this after action='prepare' so send_message and the final session share the same URL."
            },
            "exposure_strategy": {
                "type": "string",
                "enum": ["auto", "localhost", "cloud77", "tailscale-serve", "tailscale-funnel"],
                "description": "Hint passed through to the launcher template so one Plannotator launcher can support multiple exposure backends."
            },
            "command_template": {
                "type": "string",
                "description": "Optional one-off shell template override. Available placeholders: {artifact_path}, {review_target}, {review_target_arg}, {exposure_strategy}, {repo_path}."
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Launcher timeout in seconds for the initial bridge start. Default 120."
            },
            "wait_for_completion": {
                "type": "boolean",
                "description": "If true (default for review/annotate, false for prepare/last), wait synchronously for the launched Plannotator session to finish before returning."
            },
            "completion_timeout_seconds": {
                "type": "integer",
                "description": "How long to wait for the Plannotator session to complete when wait_for_completion=true. Default 3600 (60 minutes)."
            },
            "poll_interval_seconds": {
                "type": "number",
                "description": "Polling interval while waiting for session completion. Default 2 seconds."
            }
        },
        "required": ["action"]
    }
}


def plannotator_session_tool(args: dict[str, Any], **_kw) -> str:
    action = (args.get("action") or "").strip().lower()
    if action not in _DEFAULT_TEMPLATES:
        return json.dumps({"error": f"Unsupported action: {action}"})

    artifact_path = (args.get("artifact_path") or "").strip()
    review_target = (args.get("review_target") or "").strip()
    repo_path = (args.get("repo_path") or "").strip() or None
    fixed_host = (args.get("fixed_host") or "").strip() or None
    exposure_strategy = (args.get("exposure_strategy") or "auto").strip().lower() or "auto"
    launch_timeout = int(args.get("timeout_seconds") or _DEFAULT_LAUNCH_TIMEOUT_SECONDS)
    wait_for_completion = args.get("wait_for_completion")
    if wait_for_completion is None:
        wait_for_completion = action in {"review", "annotate"}
    completion_timeout = int(args.get("completion_timeout_seconds") or _DEFAULT_COMPLETION_TIMEOUT_SECONDS)
    poll_interval = float(args.get("poll_interval_seconds") or _DEFAULT_POLL_INTERVAL_SECONDS)
    poll_interval = max(0.25, poll_interval)

    if action == "annotate" and not artifact_path:
        return json.dumps({"error": "'artifact_path' is required when action='annotate'"})
    if action == "annotate" and not os.path.isabs(artifact_path):
        return json.dumps({"error": "'artifact_path' must be an absolute path"})

    template = _resolve_template(action, args.get("command_template"))
    if not template:
        env_name = _ENV_TEMPLATE_BY_ACTION[action]
        return json.dumps({
            "error": (
                f"No Plannotator launcher template configured for action '{action}'. "
                f"Set {env_name} or pass command_template directly."
            )
        })

    review_target_arg = f" {review_target}" if review_target else ""
    variables = {
        "artifact_path": artifact_path,
        "review_target": review_target,
        "review_target_arg": review_target_arg,
        "exposure_strategy": exposure_strategy,
        "repo_path": repo_path or "",
    }
    child_env = {"PLANNOTATOR_EXPOSURE_STRATEGY": exposure_strategy}
    if fixed_host:
        child_env[_PLANNOTATOR_HOST_ENV] = fixed_host

    try:
        execution = run_command_template(
            template,
            variables=variables,
            cwd=repo_path,
            timeout=launch_timeout,
            env=child_env,
        )
    except KeyError as exc:
        return json.dumps({"error": f"Command template references unknown placeholder: {exc}"})
    except Exception as exc:
        logger.exception("plannotator_session failed")
        return json.dumps({"error": f"Failed to launch Plannotator: {type(exc).__name__}: {exc}"})

    if execution["exit_code"] != 0:
        return json.dumps({
            "error": f"Plannotator launcher failed with exit code {execution['exit_code']}",
            "command": execution["command"],
            "stdout": execution["stdout"],
            "stderr": execution["stderr"],
        })

    if not execution["url"]:
        return json.dumps({
            "error": "Plannotator launcher succeeded but did not report a URL.",
            "command": execution["command"],
            "stdout": execution["stdout"],
            "stderr": execution["stderr"],
        })

    host = execution["parsed"].get("HOST") or _host_from_url(execution["url"])
    result = {
        "success": True,
        "action": action,
        "host": host,
        "url": execution["url"],
        "pid": execution["pid"],
        "log": execution["log"],
        "command": execution["command"],
        "stdout": execution["stdout"],
        "stderr": execution["stderr"],
        "exposure_strategy": exposure_strategy,
        "suggested_message": _build_suggested_message(execution["url"]),
        "waited_for_completion": False,
    }

    if not wait_for_completion:
        return json.dumps(result)

    wait_result = _wait_for_plannotator_completion(
        pid=execution.get("pid"),
        log_path=execution.get("log"),
        timeout_seconds=completion_timeout,
        poll_interval_seconds=poll_interval,
    )
    result.update(wait_result)
    result["waited_for_completion"] = True
    return json.dumps(result)


def _resolve_template(action: str, template_override: str | None) -> str:
    override = (template_override or "").strip()
    if override:
        return override
    env_template = os.getenv(_ENV_TEMPLATE_BY_ACTION[action], "").strip()
    if env_template:
        return env_template
    return _DEFAULT_TEMPLATES[action]


def _host_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc or None


def _build_suggested_message(url: str) -> str:
    return (
        f"Temporary review URL:\n{url}\n\n"
        "What to do\n"
        "- open the link\n"
        "- add comments / replacements\n"
        "- press Send Annotations when done"
    )


def _wait_for_plannotator_completion(
    *,
    pid: str | int | None,
    log_path: str | None,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    pid_int = _coerce_pid(pid)
    started = time.monotonic()
    last_log_content = _read_log_excerpt(log_path)

    if pid_int is None and not log_path:
        return {
            "completed": False,
            "timed_out": False,
            "status": "not_waitable",
            "final_log": None,
            "message": "Plannotator session could not be waited on because the launcher did not report a PID or log path.",
        }

    while True:
        elapsed = time.monotonic() - started
        process_alive = _pid_is_running(pid_int) if pid_int is not None else None
        current_log = _read_log_excerpt(log_path)
        if current_log is not None:
            last_log_content = current_log

        if process_alive is False:
            final_log = _read_log_excerpt(log_path)
            if final_log is not None:
                last_log_content = final_log
            return {
                "completed": True,
                "timed_out": False,
                "status": "completed",
                "final_log": last_log_content,
                "message": "Plannotator session completed.",
                "elapsed_seconds": round(elapsed, 2),
            }

        if elapsed >= timeout_seconds:
            return {
                "completed": False,
                "timed_out": True,
                "status": "timeout",
                "final_log": last_log_content,
                "message": f"Timed out waiting for Plannotator session after {timeout_seconds} seconds.",
                "elapsed_seconds": round(elapsed, 2),
                "session_still_running": bool(process_alive),
            }

        time.sleep(poll_interval_seconds)


def _coerce_pid(pid: str | int | None) -> int | None:
    if pid in (None, ""):
        return None
    try:
        return int(pid)
    except (TypeError, ValueError):
        return None


def _pid_is_running(pid: int | None) -> bool | None:
    if pid is None:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_log_excerpt(log_path: str | None) -> str | None:
    if not log_path:
        return None
    path = Path(log_path).expanduser()
    try:
        if not path.exists():
            return None
        data = path.read_bytes()
    except OSError:
        return None

    if len(data) > _MAX_LOG_BYTES:
        data = data[-_MAX_LOG_BYTES:]

    return data.decode("utf-8", errors="replace")


registry.register(
    name="plannotator_session",
    toolset="plannotator",
    schema=_PLANNOTATOR_SCHEMA,
    handler=plannotator_session_tool,
    emoji="📝",
)
