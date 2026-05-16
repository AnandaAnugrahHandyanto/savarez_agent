"""CLI surface for Symphony-style issue orchestration.

The implementation is intentionally small at first: parser shape and clear
placeholder command behavior. Workflow loading, validation, and execution are
added in later TDD tasks.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from symphony.config import load_config
from symphony.errors import SymphonyError
from symphony.observability import build_state_snapshot
from symphony.orchestrator import OrchestratorState, run_once
from symphony.prompt import render_prompt
from symphony.runner import HermesRunner
from symphony.tracker import LinearTrackerClient, linear_http_transport
from symphony.workflow import load_workflow, resolve_workflow_path


def build_parser(parent_subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Attach the ``symphony`` command tree to *parent_subparsers*."""

    parser = parent_subparsers.add_parser(
        "symphony",
        help="Run Symphony-style issue orchestration with Hermes agents",
        description=(
            "Poll an issue tracker, create per-issue workspaces, and run "
            "Hermes agents as Symphony workers."
        ),
    )
    subparsers = parser.add_subparsers(dest="symphony_command")

    validate = subparsers.add_parser(
        "validate",
        help="Validate a Symphony WORKFLOW.md file",
    )
    validate.add_argument(
        "workflow",
        nargs="?",
        default=None,
        help="Path to WORKFLOW.md (default: ./WORKFLOW.md)",
    )
    validate.add_argument("--json", action="store_true", help="Emit JSON output")

    run = subparsers.add_parser(
        "run",
        help="Run the Symphony orchestrator",
    )
    run.add_argument(
        "workflow",
        nargs="?",
        default=None,
        help="Path to WORKFLOW.md (default: ./WORKFLOW.md)",
    )
    run.add_argument("--once", action="store_true", help="Run one poll/dispatch cycle")
    run.add_argument("--max-cycles", type=int, default=None, help="Stop after N poll cycles (default: run forever)")
    run.add_argument("--port", type=int, default=None, help="Enable status HTTP server on port")
    run.add_argument("--json", action="store_true", help="Emit JSON output")

    state = subparsers.add_parser(
        "state",
        help="Print Symphony runtime state",
    )
    state.add_argument(
        "workflow",
        nargs="?",
        default=None,
        help="Path to WORKFLOW.md (default: ./WORKFLOW.md)",
    )
    state.add_argument("--json", action="store_true", help="Emit JSON output")

    return parser


def _emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _error_payload(error: SymphonyError) -> dict[str, Any]:
    return {"ok": False, "error": error.to_payload()}


def _workflow_path(raw_path: str | None) -> Path:
    return resolve_workflow_path(raw_path)


def symphony_command(args: argparse.Namespace) -> int:
    """Dispatch ``hermes symphony`` subcommands."""

    command = getattr(args, "symphony_command", None)
    if command in {None, ""}:
        print("usage: hermes symphony <validate|run|state> [WORKFLOW.md]")
        return 1

    if command == "validate":
        try:
            workflow_path = _workflow_path(getattr(args, "workflow", None))
            workflow = load_workflow(workflow_path)
            config = load_config(workflow.config, workflow_dir=workflow_path.parent)
            render_prompt(workflow.prompt_template, issue=_sample_issue_context(), attempt=1)
        except SymphonyError as exc:
            if getattr(args, "json", False):
                _emit_json(_error_payload(exc))
            else:
                print(f"Error [{exc.code}]: {exc.message}")
            return 1
        if getattr(args, "json", False):
            _emit_json(
                {
                    "ok": True,
                    "workflow": str(workflow_path),
                    "agent": {
                        "runner": config.agent.runner,
                        "max_turns": config.agent.max_turns,
                        "max_concurrent_agents": config.agent.max_concurrent_agents,
                    },
                    "hermes": {"mode": config.hermes.mode, "command": config.hermes.command},
                    "workspace": {"root": str(config.workspace.root)},
                }
            )
        else:
            print(f"Symphony workflow is valid: {workflow_path}")
        return 0

    if command == "run":
        try:
            workflow_path = _workflow_path(getattr(args, "workflow", None))
            workflow = load_workflow(workflow_path)
            config = load_config(workflow.config, workflow_dir=workflow_path.parent)
            render_prompt(workflow.prompt_template, issue=_sample_issue_context(), attempt=1)
            if getattr(args, "port", None) is not None:
                raise SymphonyError(
                    "unsupported_status_server",
                    "hermes symphony run --port is reserved for a future status HTTP server and is not implemented yet.",
                )
        except SymphonyError as exc:
            if getattr(args, "json", False):
                _emit_json(_error_payload(exc))
            else:
                print(f"Error [{exc.code}]: {exc.message}")
            return 1
        if getattr(args, "once", False):
            payload = _run_once_payload(config, workflow.prompt_template, workflow_path)
        else:
            payload = _run_loop_payload(
                config,
                workflow.prompt_template,
                workflow_path,
                max_cycles=getattr(args, "max_cycles", None),
            )
        if getattr(args, "json", False):
            _emit_json(payload)
        else:
            if payload.get("skipped") == "missing_tracker_api_key":
                print("Symphony run --once skipped: tracker.api_key is not configured.")
            else:
                print(f"Symphony run completed ({payload['mode']}): dispatched {payload['dispatched']} issue(s).")
        return 0

    if command == "state":
        snapshot = build_state_snapshot(OrchestratorState())
        raw_workflow = getattr(args, "workflow", None)
        if raw_workflow is not None or Path("WORKFLOW.md").exists():
            try:
                workflow_path = _workflow_path(raw_workflow)
                workflow = load_workflow(workflow_path)
                config = load_config(workflow.config, workflow_dir=workflow_path.parent)
                snapshot = _load_state_snapshot(config) or snapshot
            except SymphonyError as exc:
                if getattr(args, "json", False):
                    _emit_json(_error_payload(exc))
                else:
                    print(f"Error [{exc.code}]: {exc.message}")
                return 1
        if getattr(args, "json", False):
            _emit_json({"ok": True, "snapshot": snapshot})
        else:
            print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0

    print(f"Unknown symphony subcommand: {command}")
    return 1


def _sample_issue_context() -> dict[str, str]:
    return {
        "id": "sample-issue-id",
        "identifier": "SAMPLE-1",
        "title": "Sample Symphony validation issue",
        "url": "https://linear.app/example/issue/SAMPLE-1",
        "state": "Todo",
    }


def _run_once_payload(
    config: Any,
    workflow_prompt_template: str,
    workflow_path: Path,
    *,
    state: OrchestratorState | None = None,
    wait_for_completion: bool = True,
) -> dict[str, Any]:
    base = {
        "ok": True,
        "mode": "once",
        "workflow": str(workflow_path),
        "runner": config.agent.runner,
    }
    if config.agent.runner != "hermes":
        raise SymphonyError("unsupported_agent_runner", "Only agent.runner: hermes is executable by hermes symphony run today.")
    orchestration_state = state or OrchestratorState()
    if not config.tracker.api_key:
        payload = {
            **base,
            "dispatched": 0,
            "issue_identifiers": [],
            "skipped": "missing_tracker_api_key",
            "snapshot": build_state_snapshot(orchestration_state),
        }
        _try_persist_state_snapshot(config, payload["snapshot"])
        return payload

    tracker = LinearTrackerClient(linear_http_transport(config.tracker.api_key))
    runner = HermesRunner(config=config.hermes)
    result = run_once(
        config=config,
        workflow_prompt_template=workflow_prompt_template,
        tracker=tracker,
        runner=runner,
        state=orchestration_state,
        state_observer=lambda snapshot: (_try_persist_state_snapshot(config, snapshot), None)[1],
        wait_for_completion=wait_for_completion,
    )
    payload = {
        **base,
        "dispatched": result.dispatched,
        "issue_identifiers": result.issue_identifiers,
        "snapshot": result.snapshot,
    }
    _try_persist_state_snapshot(config, payload["snapshot"])
    return payload


def _run_loop_payload(
    config: Any,
    workflow_prompt_template: str,
    workflow_path: Path,
    *,
    max_cycles: int | None,
) -> dict[str, Any]:
    cycles = 0
    total_dispatched = 0
    last_payload: dict[str, Any] | None = None
    try:
        orchestration_state = OrchestratorState()
        while max_cycles is None or cycles < max_cycles:
            try:
                last_payload = _run_once_payload(
                    config,
                    workflow_prompt_template,
                    workflow_path,
                    state=orchestration_state,
                    wait_for_completion=False,
                )
            except Exception as exc:  # noqa: BLE001 - runner daemon survives transient tracker/setup errors.
                last_payload = {
                    "ok": False,
                    "mode": "once",
                    "workflow": str(workflow_path),
                    "runner": config.agent.runner,
                    "dispatched": 0,
                    "error": {"code": type(exc).__name__, "message": str(exc)},
                    "snapshot": build_state_snapshot(orchestration_state),
                }
                _try_persist_state_snapshot(config, last_payload["snapshot"])
            cycles += 1
            total_dispatched += int(last_payload.get("dispatched", 0))
            if max_cycles is not None and cycles >= max_cycles:
                break
            time.sleep(max(0, config.polling.interval_ms) / 1000)
    except KeyboardInterrupt:
        pass

    return {
        "ok": True,
        "mode": "loop",
        "workflow": str(workflow_path),
        "runner": config.agent.runner,
        "cycles": cycles,
        "dispatched": total_dispatched,
        "last": last_payload,
    }


def _state_path(config: Any) -> Path:
    return Path(config.workspace.root) / ".symphony" / "state.json"


def _persist_state_snapshot(config: Any, snapshot: dict[str, Any]) -> None:
    path = _state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _try_persist_state_snapshot(config: Any, snapshot: dict[str, Any]) -> bool:
    try:
        _persist_state_snapshot(config, snapshot)
    except OSError:
        snapshot["state_persisted"] = False
        return False
    snapshot["state_persisted"] = True
    return True


def _load_state_snapshot(config: Any) -> dict[str, Any] | None:
    path = _state_path(config)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
