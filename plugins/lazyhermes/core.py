from __future__ import annotations

import json
import re
import shlex
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from hermes_constants import get_hermes_home
except Exception:
    import os

    def get_hermes_home() -> Path:
        val = (os.environ.get("HERMES_HOME") or "").strip()
        return Path(val).expanduser() if val else Path.home() / ".hermes"


ULTRAWORK_PATTERN = re.compile(r"\b(?:ultrawork|ulw)\b", re.IGNORECASE)
DIRECT_ULW_PATTERN = re.compile(r"^\s*(?:ulw|ultrawork)\b\s+(?P<task>.+?)\s*$", re.IGNORECASE | re.DOTALL)
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")

ULTRAWORK_CONTEXT = "\n".join(
    [
        "<lazyhermes-ultrawork>",
        "The user invoked Ultrawork/LazyHermes. Operate in a durable, evidence-first loop:",
        "- restate the concrete completion promise before changing files;",
        "- keep the implementation scoped to the current repository and existing Hermes patterns;",
        "- use focused tests and manual verification evidence before claiming done;",
        "- preserve unrelated user changes and avoid destructive git commands;",
        "- keep local state, plans, and evidence under plans/ or .hermes/lazyhermes when useful.",
        "",
        "<lazyhermes-goal-bootstrap>",
        "When this turn has a concrete objective, reflect LazyCodex goal semantics through model-facing tools:",
        "- First call get_goal.",
        "- If no active goal exists, call create_goal with objective and status only.",
        '- The create_goal payload shape is exactly: {"objective": "<current concrete objective>", "status": "active"}.',
        "- If get_goal reports the same objective as active, continue without creating a duplicate.",
        "- Use update_goal only after verified completion or a real unrecoverable blocker.",
        "</lazyhermes-goal-bootstrap>",
        "</lazyhermes-ultrawork>",
    ]
)


@dataclass(frozen=True)
class CommandArgs:
    positional: list[str]
    options: dict[str, str | bool]


def slugify(text: str, fallback: str = "lazyhermes-plan") -> str:
    lowered = text.strip().lower()
    slug = _SLUG_PATTERN.sub("-", lowered).strip("-")
    return (slug[:60].strip("-") or fallback)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_id(prefix: str = "run") -> str:
    return f"{prefix}-{utc_now().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def parse_args(raw_args: str) -> CommandArgs:
    try:
        tokens = shlex.split(raw_args or "")
    except ValueError as exc:
        raise ValueError(f"could not parse arguments: {exc}") from exc

    positional: list[str] = []
    options: dict[str, str | bool] = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token.startswith("--"):
            positional.append(token)
            i += 1
            continue

        key_value = token[2:]
        if not key_value:
            i += 1
            continue
        if "=" in key_value:
            key, value = key_value.split("=", 1)
            options[key] = value
            i += 1
            continue
        key = key_value
        if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
            options[key] = tokens[i + 1]
            i += 2
        else:
            options[key] = True
            i += 1

    return CommandArgs(positional=positional, options=options)


def workspace_from_option(value: str | bool | None) -> Path:
    if isinstance(value, str) and value.strip():
        return Path(value).expanduser().resolve()
    return Path.cwd().resolve()


def plan_dir(workspace: Path) -> Path:
    return workspace / "plans"


def lazyhermes_dir(workspace: Path) -> Path:
    return workspace / ".hermes" / "lazyhermes"


def event_log_path() -> Path:
    return get_hermes_home() / "lazyhermes" / "events.jsonl"


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def record_event(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "timestamp": utc_now().isoformat(),
        **fields,
    }
    try:
        append_jsonl(event_log_path(), payload)
    except OSError:
        pass


def pre_llm_call(**kwargs: Any) -> dict[str, str] | None:
    user_message = str(kwargs.get("user_message") or "")
    if "<lazyhermes-run-context>" in user_message:
        return None
    if not ULTRAWORK_PATTERN.search(user_message):
        return None
    direct = DIRECT_ULW_PATTERN.match(user_message)
    run_context = ""
    if direct:
        task = direct.group("task").strip()
        if task:
            workspace = Path.cwd().resolve()
            run_dir = write_run_state(
                workspace,
                task=task,
                command="ulw",
            )
            run_context = "\n\n" + build_run_agent_message(load_run_state(run_dir))
    record_event(
        "ultrawork_trigger",
        session_id=str(kwargs.get("session_id") or ""),
        platform=str(kwargs.get("platform") or ""),
    )
    return {"context": ULTRAWORK_CONTEXT + run_context}


def build_goal_instruction(
    objective: str,
    *,
    plan: Path | None = None,
    workspace: Path | None = None,
) -> str:
    objective = objective.strip() or "Complete the requested LazyHermes task with evidence."
    create_goal = {
        "objective": objective,
        "status": "active",
    }
    plan_line = f"Plan: {plan}" if plan else "Plan: none"
    workspace_line = f"Workspace: {workspace}" if workspace else "Workspace: current"
    return "\n".join(
        [
            "<lazyhermes-goal-instruction>",
            "LazyCodex-style Codex goal handoff for Hermes.",
            workspace_line,
            plan_line,
            "",
            "Codex goal integration constraints:",
            "- Do not type /goal and do not stop after creating a local LazyHermes plan.",
            "- First call get_goal. If no active goal exists, call create_goal with the payload below.",
            "- If get_goal reports the same objective as active, continue without creating a duplicate.",
            "- If get_goal reports a different active goal, finish or checkpoint it before starting this plan.",
            "- Keep goals unlimited; do not add numeric budgets or limits.",
            "- Call update_goal({\"status\": \"complete\"}) only after the requested work is implemented, tested, and manually verified.",
            "- If blocked, preserve evidence and call update_goal({\"status\": \"blocked\"}) only when no meaningful recovery path remains.",
            "",
            "create_goal payload:",
            json.dumps(create_goal, indent=2, sort_keys=True),
            "</lazyhermes-goal-instruction>",
        ]
    )


def create_plan(brief: str, workspace: Path | None = None) -> Path:
    brief = brief.strip()
    if not brief:
        raise ValueError('usage: /ulw-plan "what to build"')

    root = (workspace or Path.cwd()).resolve()
    out_dir = plan_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slugify(brief)}.md"
    if path.exists():
        path = out_dir / f"{slugify(brief)}-{utc_now().strftime('%H%M%S')}.md"

    now = utc_now().isoformat()
    content = "\n".join(
        [
            f"# {brief}",
            "",
            f"Created: {now}",
            "Source: lazyhermes",
            "",
            "## Completion Promise",
            "",
            "- [ ] Define the user-visible outcome in one sentence.",
            "",
            "## Constraints",
            "",
            "- [ ] Preserve unrelated user changes.",
            "- [ ] Prefer existing Hermes patterns and local APIs.",
            "- [ ] Keep LazyHermes state local to this workspace.",
            "",
            "## Implementation Steps",
            "",
            "- [ ] Inspect the relevant files and tests.",
            "- [ ] Make the smallest coherent implementation.",
            "- [ ] Add or update focused tests.",
            "- [ ] Run targeted verification and capture evidence.",
            "",
            "## Verification Evidence",
            "",
            "- [ ] Record commands, outputs, screenshots, or manual checks needed to trust the result.",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
    record_event("plan_created", workspace=str(root), plan=str(path), brief=brief)
    return path


def unchecked_items(markdown: str) -> list[str]:
    items: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ] "):
            items.append(stripped[6:].strip())
    return items


def find_plan(name: str, workspace: Path) -> Path | None:
    plans = plan_dir(workspace)
    if not plans.exists():
        return None

    raw = name.strip()
    if not raw:
        candidates = sorted(plans.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None

    direct = Path(raw).expanduser()
    if direct.exists():
        return direct.resolve()

    slug = slugify(raw, fallback=raw)
    candidates = [
        plans / raw,
        plans / f"{raw}.md",
        plans / slug,
        plans / f"{slug}.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def write_run_state(
    workspace: Path,
    *,
    task: str,
    command: str,
    plan: Path | None = None,
    completion_promise: str = "",
    strategy: str = "continue",
) -> Path:
    rid = run_id("lazyhermes")
    run_dir = lazyhermes_dir(workspace) / "runs" / rid
    evidence_dir = run_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "run_id": rid,
        "created_at": utc_now().isoformat(),
        "workspace": str(workspace),
        "command": command,
        "task": task,
        "completion_promise": completion_promise,
        "strategy": strategy,
        "plan": str(plan) if plan else "",
        "evidence_dir": str(evidence_dir),
    }
    (run_dir / "state.json").write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    append_jsonl(run_dir / "ledger.jsonl", {"event": "run_started", **state})
    record_event("run_started", workspace=str(workspace), command=command, run_id=rid)
    return run_dir


def load_run_state(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "state.json").read_text(encoding="utf-8"))


def build_run_agent_message(state: dict[str, Any]) -> str:
    plan_line = f"\nPlan: {state['plan']}" if state.get("plan") else ""
    promise = state.get("completion_promise") or "Complete the requested task with evidence."
    plan_path = Path(state["plan"]) if state.get("plan") else None
    workspace = Path(state["workspace"]) if state.get("workspace") else None
    return "\n".join(
        [
            state["task"],
            "",
            build_goal_instruction(state["task"], plan=plan_path, workspace=workspace),
            "",
            "<lazyhermes-run-context>",
            f"run_id: {state['run_id']}",
            f"workspace: {state['workspace']}",
            f"evidence_dir: {state['evidence_dir']}",
            f"ledger: {Path(state['evidence_dir']).parent / 'ledger.jsonl'}",
            f"strategy: {state['strategy']}",
            f"completion_promise: {promise}",
            f"task: {state['task']}{plan_line}",
            "",
            "Execute this LazyHermes request now. Inspect the workspace as needed,",
            "keep useful evidence under evidence_dir, append meaningful progress to the ledger,",
            "and answer the user with the result instead of stopping after run creation.",
            "</lazyhermes-run-context>",
        ]
    )


def build_dispatch_result(run_dir: Path, *, display: str) -> dict[str, str]:
    state = load_run_state(run_dir)
    return {
        "display": display,
        "agent_message": build_run_agent_message(state),
        "run_dir": str(run_dir),
    }


def _join_positional(positional: Iterable[str]) -> str:
    return " ".join(part for part in positional if part).strip()


def build_plan_agent_message(brief: str, plan: Path, workspace: Path) -> str:
    return "\n".join(
        [
            brief,
            "",
            build_goal_instruction(brief, plan=plan, workspace=workspace),
            "",
            "<lazyhermes-plan-context>",
            f"workspace: {workspace}",
            f"plan: {plan}",
            "",
            "Execute this LazyHermes plan now. Use the plan as a durable artifact,",
            "but drive the actual Codex goal loop through the model-facing goal tools",
            "before implementation and after verification.",
            "</lazyhermes-plan-context>",
        ]
    )


def command_ulw_plan(raw_args: str) -> dict[str, str]:
    args = parse_args(raw_args)
    workspace = workspace_from_option(args.options.get("worktree"))
    brief = _join_positional(args.positional)
    path = create_plan(brief, workspace)
    return {
        "display": f"Created LazyHermes plan: {path}\nForwarding goal bootstrap to Hermes agent now.",
        "agent_message": build_plan_agent_message(brief, path, workspace),
        "plan": str(path),
    }


def _command_ulw_dispatch(raw_args: str, *, command: str) -> dict[str, str]:
    args = parse_args(raw_args)
    workspace = workspace_from_option(args.options.get("worktree"))
    task = _join_positional(args.positional)
    if not task:
        raise ValueError('usage: /ulw-loop "task" [--completion-promise TEXT] [--strategy reset|continue]')
    completion = str(args.options.get("completion-promise") or "")
    strategy = str(args.options.get("strategy") or "continue")
    if strategy not in {"continue", "reset"}:
        raise ValueError("--strategy must be either 'continue' or 'reset'")
    run_dir = write_run_state(
        workspace,
        task=task,
        command=command,
        completion_promise=completion,
        strategy=strategy,
    )
    promise = f"\nCompletion promise: {completion}" if completion else ""
    display = (
        f"Started LazyHermes Ultrawork run: {run_dir}"
        f"{promise}\nForwarding task to Hermes agent now."
    )
    return build_dispatch_result(run_dir, display=display)


def command_ulw_loop(raw_args: str) -> dict[str, str]:
    return _command_ulw_dispatch(raw_args, command="ulw-loop")


def command_ulw(raw_args: str) -> dict[str, str]:
    return _command_ulw_dispatch(raw_args, command="ulw")


def command_start_work(raw_args: str) -> str:
    args = parse_args(raw_args)
    workspace = workspace_from_option(args.options.get("worktree"))
    plan_name = _join_positional(args.positional)
    plan = find_plan(plan_name, workspace)
    if plan is None:
        raise ValueError(f"no plan found for '{plan_name or 'latest'}' in {plan_dir(workspace)}")

    text = plan.read_text(encoding="utf-8")
    open_items = unchecked_items(text)
    if args.options.get("dry-run"):
        preview = "\n".join(f"- {item}" for item in open_items[:8]) or "- no unchecked items found"
        return f"LazyHermes dry-run for {plan}:\n{preview}"

    run_dir = write_run_state(
        workspace,
        task=f"Start work from {plan.name}",
        command="start-work",
        plan=plan,
    )
    first_items = "\n".join(f"- {item}" for item in open_items[:5]) or "- no unchecked items found"
    return (
        f"Started LazyHermes work run: {run_dir}\n"
        f"Plan: {plan}\n"
        f"Open items:\n{first_items}"
    )
