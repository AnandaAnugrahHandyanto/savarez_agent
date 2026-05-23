"""Core BMad/Symphony workflow helpers.

This module keeps the plugin thin: state persistence, plan/story/run/proof
builders, and human-readable formatting all live here so the CLI, slash
command, tools, and hooks share one implementation path.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    from hermes_constants import get_hermes_home
except Exception:  # pragma: no cover - defensive fallback for tests/import order
    def get_hermes_home() -> Path:  # type: ignore[no-redef]
        return (Path.home() / ".hermes").resolve()

PLUGIN_NAME = "bmad-symphony"
STATE_VERSION = 1
HISTORY_LIMIT = 25
BMAD_SOURCE_URL = "https://docs.bmad-method.org/llms-full.txt"

DEFAULT_TOOLSETS = ["terminal", "file", "delegation", "search", "web", "todo"]

BMAD_SOURCE_DERIVATION = {
    "source": BMAD_SOURCE_URL,
    "rule": (
        "BMAD-specific guidance is derived from the extracted BMAD documentation "
        "artifact and user-provided context. Symphony/delegation is a Hermes "
        "execution wrapper, not a BMAD source concept."
    ),
    "reference_file": "plugins/bmad_symphony/source/bmad_llms_extract.md",
}

BMAD_PHASES = [
    "Analysis — optional brainstorming, research, product brief, or PRFAQ",
    "Planning — required requirements via PRD or spec",
    "Solutioning — architecture and technical work breakdown",
    "Implementation — build epic by epic, story by story",
]

BMAD_TRACKS = [
    "Quick Flow — bug fixes, simple features, clear scope; tech-spec only",
    "BMad Method — products, platforms, complex features; PRD + Architecture + UX",
    "Enterprise — compliance or multi-tenant systems; PRD + Architecture + Security + DevOps",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_dir() -> Path:
    return get_hermes_home() / "plugins" / PLUGIN_NAME


def state_file() -> Path:
    return state_dir() / "state.json"


def _default_state() -> Dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "active": False,
        "mode": "idle",
        "current_goal": "",
        "context": "",
        "intake": {},
        "story": {},
        "run": {},
        "proof": {},
        "history": [],
        "updated_at": now_iso(),
    }


def load_state() -> Dict[str, Any]:
    path = state_file()
    if not path.exists():
        return _default_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_state()
    if not isinstance(raw, dict):
        return _default_state()
    base = _default_state()
    base.update(raw)
    base.setdefault("history", [])
    return base


def save_state(state: Dict[str, Any]) -> None:
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["updated_at"] = now_iso()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def clear_state() -> Dict[str, Any]:
    state = _default_state()
    save_state(state)
    return state


def _truncate(text: str, limit: int = 280) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _split_lines(text: str) -> List[str]:
    lines = []
    for raw in (text or "").splitlines():
        line = raw.strip(" -\t")
        if line:
            lines.append(line)
    return lines


def _coerce_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_lines(value)
    if isinstance(value, Iterable):
        items = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                items.append(text)
        return items
    return []


def _history_entry(event: str, summary: str, **data: Any) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "ts": now_iso(),
        "event": event,
        "summary": summary,
    }
    if data:
        entry["data"] = data
    return entry


def _append_history(state: Dict[str, Any], event: str, summary: str, **data: Any) -> Dict[str, Any]:
    history = list(state.get("history", []))
    history.append(_history_entry(event, summary, **data))
    state["history"] = history[-HISTORY_LIMIT:]
    return state


def update_state(
    *,
    mode: str,
    goal: str = "",
    context: str = "",
    intake: Optional[Dict[str, Any]] = None,
    story: Optional[Dict[str, Any]] = None,
    run: Optional[Dict[str, Any]] = None,
    proof: Optional[Dict[str, Any]] = None,
    active: Optional[bool] = None,
    event: str = "update",
    summary: str = "state updated",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    state = load_state()
    state["mode"] = mode
    if goal:
        state["current_goal"] = goal
    if context:
        state["context"] = context
    if intake is not None:
        state["intake"] = intake
    if story is not None:
        state["story"] = story
    if run is not None:
        state["run"] = run
    if proof is not None:
        state["proof"] = proof
    if active is not None:
        state["active"] = active
    if extra:
        state.update(extra)
    _append_history(state, event, summary, goal=goal or state.get("current_goal", ""), mode=mode)
    save_state(state)
    return state


def record_event(event: str, summary: str, **data: Any) -> Dict[str, Any]:
    state = load_state()
    _append_history(state, event, summary, **data)
    save_state(state)
    return state


def current_goal(state: Optional[Dict[str, Any]] = None) -> str:
    source = state if state is not None else load_state()
    return str(source.get("current_goal", "") or "").strip()


def _goal_title(goal: str) -> str:
    words = [w for w in _truncate(goal, 80).replace("/", " ").split() if w]
    if not words:
        return "BMad / Symphony initiative"
    return " ".join(words[:8]).strip(" ,.")


def _collect_acceptance(goal: str, context: str = "", acceptance: Any = None) -> List[str]:
    items = _coerce_list(acceptance)
    if items:
        return items
    collected = [
        f"The requested outcome for '{_truncate(goal, 90)}' is delivered end-to-end.",
        "The implementation is covered by proof-of-work: tests, checks, or reproducible validation.",
        "The final handoff includes any caveats, follow-ups, or rollback notes.",
    ]
    if context:
        collected.append("The solution respects the provided context and constraints.")
    return collected


def build_intake(
    *,
    goal: str,
    context: str = "",
    constraints: Any = None,
    repo_scope: str = "",
    audience: str = "agent",
) -> Dict[str, Any]:
    goal = (goal or "").strip()
    context = (context or "").strip()
    constraints_list = _coerce_list(constraints)
    scope = repo_scope.strip()
    parallel_axes = _coerce_list(constraints if isinstance(constraints, (list, tuple)) else [])
    if not parallel_axes and context:
        parallel_axes = _split_lines(context)[:3]

    deliverables = [
        "A BMad track recommendation: Quick Flow, BMad Method, or Enterprise.",
        "A phase-aware next workflow recommendation grounded in the BMAD phase model.",
        "A list of expected BMAD artifacts for the selected track and phase.",
    ]

    if scope:
        deliverables.append(f"Scope is limited to: {scope}.")

    assumptions = [
        "Start with bmad-help whenever the next BMAD workflow is uncertain.",
        "Use a fresh chat for each BMAD workflow to avoid context-limit and contamination issues.",
    ]
    if context:
        assumptions.append("User-provided context is treated as the source of truth for constraints and preferences.")

    risks = [
        "Choosing a track by story count alone can be misleading; BMAD says to choose by planning need.",
        "Skipping planning/solutioning artifacts can leave implementation stories under-specified.",
    ]

    return {
        "title": _goal_title(goal),
        "goal": goal,
        "context": context,
        "audience": audience,
        "scope": scope,
        "deliverables": deliverables,
        "assumptions": assumptions,
        "constraints": constraints_list,
        "parallel_axes": parallel_axes,
        "risks": risks,
        "source_derivation": BMAD_SOURCE_DERIVATION,
        "bmad_phases": BMAD_PHASES,
        "planning_tracks": BMAD_TRACKS,
        "recommended_flow": [
            "Install/select BMad Method if not already installed",
            "Run bmad-help to detect current artifacts and next workflow",
            "Use the appropriate phase workflow in a fresh chat",
            "For implementation, use sprint planning then create-story/dev-story/code-review per story",
        ],
        "expected_artifacts": [
            "_bmad/ for agents, workflows, tasks, and configuration",
            "_bmad-output/ for generated artifacts",
            "PRD/addendum/decision-log for BMad Method and Enterprise planning",
            "Architecture document before epics and stories for BMad Method and Enterprise",
            "sprint-status.yaml before story implementation",
        ],
        "next_action": "Run bmad-help, then choose the next BMAD workflow from the extracted source model.",
    }


def build_story(
    *,
    goal: str,
    context: str = "",
    acceptance: Any = None,
    out_of_scope: Any = None,
    implementation_notes: Any = None,
) -> Dict[str, Any]:
    goal = (goal or "").strip()
    acceptance_list = _collect_acceptance(goal, context=context, acceptance=acceptance)
    out_of_scope_list = _coerce_list(out_of_scope) or [
        "Skipping the BMAD phase/workflow sequence without an explicit reason",
        "Adding BMAD process claims that are not present in the extracted source model",
    ]
    notes_list = _coerce_list(implementation_notes) or [
        "Use a fresh chat for each BMAD workflow.",
        "For implementation, follow the BMAD story cycle: bmad-create-story, bmad-dev-story, bmad-code-review.",
    ]

    return {
        "title": _goal_title(goal),
        "user_story": f"As a user, I want {_truncate(goal, 120)} so that the requested outcome is achieved.",
        "goal": goal,
        "context": context.strip(),
        "source_derivation": BMAD_SOURCE_DERIVATION,
        "acceptance_criteria": acceptance_list,
        "out_of_scope": out_of_scope_list,
        "implementation_notes": notes_list,
        "bmad_phase_model": BMAD_PHASES,
        "bmad_story_cycle": [
            "bmad-create-story — create story file from epic",
            "bmad-dev-story — implement the story",
            "bmad-code-review — quality validation (recommended)",
        ],
    }


def _default_worker_tasks(goal: str, parallelism: int) -> List[Dict[str, Any]]:
    parallelism = max(1, parallelism)
    templates = [
        "Derive the current BMAD phase, planning track, and next workflow from the extracted source model for: {goal}",
        "Inspect project artifacts (_bmad/, _bmad-output/, PRD, architecture, epics/stories, sprint-status.yaml) for: {goal}",
        "Prepare the next BMAD workflow handoff using only extracted-source BMAD terms for: {goal}",
        "Verify the handoff cites source-derived BMAD workflows and separates Hermes execution details from BMAD claims for: {goal}",
    ]
    tasks: List[Dict[str, Any]] = []
    for idx in range(parallelism):
        tasks.append({"goal": templates[idx % len(templates)].format(goal=_truncate(goal, 110))})
    return tasks


def build_run_plan(
    *,
    goal: str,
    context: str = "",
    work_items: Any = None,
    parallelism: int = 3,
    toolsets: Any = None,
    auto_dispatch: bool = False,
) -> Dict[str, Any]:
    goal = (goal or "").strip()
    context = (context or "").strip()
    tasks = []
    if isinstance(work_items, Sequence) and not isinstance(work_items, (str, bytes)):
        for item in work_items:
            if isinstance(item, dict):
                task_goal = str(item.get("goal", "")).strip()
                if not task_goal:
                    continue
                tasks.append({
                    "goal": task_goal,
                    "context": str(item.get("context", "")).strip(),
                    "toolsets": _coerce_list(item.get("toolsets")) or DEFAULT_TOOLSETS,
                })
            else:
                text = str(item).strip()
                if text:
                    tasks.append({"goal": text, "toolsets": DEFAULT_TOOLSETS})
    if not tasks:
        tasks = _default_worker_tasks(goal, parallelism)
        for task in tasks:
            task["toolsets"] = _coerce_list(toolsets) or DEFAULT_TOOLSETS

    recommended_delegate_payload = {
        "role": "orchestrator" if len(tasks) > 1 else "leaf",
        "context": context,
        "toolsets": _coerce_list(toolsets) or DEFAULT_TOOLSETS,
    }
    if len(tasks) > 1:
        recommended_delegate_payload["tasks"] = tasks
    else:
        recommended_delegate_payload["goal"] = goal

    return {
        "goal": goal,
        "context": context,
        "parallelism": max(1, parallelism),
        "source_derivation": BMAD_SOURCE_DERIVATION,
        "mode": "batch" if len(tasks) > 1 else "single",
        "proof_gate": [
            "BMAD-specific statements cite the extracted source model or user-provided context.",
            "Hermes/Symphony delegation details are labeled as execution wrapper behavior, not BMAD doctrine.",
            "The next recommended workflow matches the current phase/artifact state.",
        ],
        "tasks": tasks,
        "auto_dispatch": bool(auto_dispatch),
        "recommended_delegate_payload": recommended_delegate_payload,
    }


def evaluate_proof(
    *,
    goal: str,
    evidence: Any = None,
    criteria: Any = None,
    tests: Any = None,
    files_changed: Any = None,
    notes: str = "",
) -> Dict[str, Any]:
    evidence_text = "\n".join(_coerce_list(evidence)) or str(evidence or "").strip()
    criteria_list = _collect_acceptance(goal, acceptance=criteria)
    tests_list = _coerce_list(tests)
    files_list = _coerce_list(files_changed)
    note_text = (notes or "").strip()

    score = 0
    if evidence_text:
        score += 1
    if tests_list:
        score += 1
    if files_list:
        score += 1
    if any(token in evidence_text.lower() for token in ("pass", "passed", "green", "verified", "done")):
        score += 1
    if note_text:
        score += 1

    missing = []
    if not evidence_text:
        missing.append("evidence")
    if not tests_list:
        missing.append("tests or checks")
    if not files_list:
        missing.append("files changed or touched artifacts")

    status = "pass" if score >= 4 and not missing else "needs_more_work"
    return {
        "goal": goal,
        "status": status,
        "score": score,
        "criteria": criteria_list,
        "source_derivation": BMAD_SOURCE_DERIVATION,
        "tests": tests_list,
        "files_changed": files_list,
        "evidence": evidence_text,
        "missing": missing,
        "next_steps": [
            "Add the missing proof if any",
            "Run the smallest useful validation again",
            "Summarize what can be reviewed safely",
        ],
    }


def summarize_state(state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source = state if state is not None else load_state()
    return {
        "version": source.get("version", STATE_VERSION),
        "active": bool(source.get("active", False)),
        "mode": source.get("mode", "idle"),
        "current_goal": source.get("current_goal", ""),
        "context": source.get("context", ""),
        "intake": source.get("intake", {}),
        "story": source.get("story", {}),
        "run": source.get("run", {}),
        "proof": source.get("proof", {}),
        "history": source.get("history", []),
        "updated_at": source.get("updated_at", ""),
    }


def format_bullets(items: Sequence[str], indent: str = "- ") -> str:
    return "\n".join(f"{indent}{item}" for item in items)


def format_intake(plan: Dict[str, Any]) -> str:
    lines = [f"BMad intake: {plan.get('title', 'initiative')}"]
    if plan.get("goal"):
        lines.append(f"Goal: {plan['goal']}")
    if plan.get("context"):
        lines.append(f"Context: {plan['context']}")
    if plan.get("scope"):
        lines.append(f"Scope: {plan['scope']}")
    lines.append("")
    lines.append("Deliverables:")
    lines.append(format_bullets(plan.get("deliverables", []), indent="  - "))
    lines.append("")
    lines.append("Assumptions:")
    lines.append(format_bullets(plan.get("assumptions", []), indent="  - "))
    lines.append("")
    lines.append("Risks:")
    lines.append(format_bullets(plan.get("risks", []), indent="  - "))
    lines.append("")
    lines.append("Next action: " + str(plan.get("next_action", "")))
    return "\n".join(lines).strip()


def format_story(story: Dict[str, Any]) -> str:
    lines = [f"Story: {story.get('title', 'initiative')}"]
    if story.get("user_story"):
        lines.append(story["user_story"])
    lines.extend(["", "Acceptance criteria:"])
    lines.append(format_bullets(story.get("acceptance_criteria", []), indent="  - "))
    lines.extend(["", "Out of scope:"])
    lines.append(format_bullets(story.get("out_of_scope", []), indent="  - "))
    lines.extend(["", "Implementation notes:"])
    lines.append(format_bullets(story.get("implementation_notes", []), indent="  - "))
    lines.extend(["", "Proof requirements:"])
    lines.append(format_bullets(story.get("proof_requirements", []), indent="  - "))
    return "\n".join(lines).strip()


def format_run_plan(run: Dict[str, Any]) -> str:
    lines = [f"Symphony run plan for: {run.get('goal', '') or 'current initiative'}"]
    if run.get("context"):
        lines.append(f"Context: {run['context']}")
    lines.extend(["", f"Parallelism: {run.get('parallelism', 1)}", "", "Worker tasks:"])
    for idx, task in enumerate(run.get("tasks", []), start=1):
        lines.append(f"  {idx}. {task.get('goal', '')}")
        toolsets = task.get("toolsets") or []
        if toolsets:
            lines.append(f"     toolsets: {', '.join(toolsets)}")
        task_context = task.get("context", "")
        if task_context:
            lines.append(f"     context: {task_context}")
    lines.extend(["", "Proof gate:"])
    lines.append(format_bullets(run.get("proof_gate", []), indent="  - "))
    return "\n".join(lines).strip()


def format_proof(proof: Dict[str, Any]) -> str:
    lines = [f"Proof gate: {proof.get('status', 'unknown')}"]
    lines.append(f"Score: {proof.get('score', 0)}")
    if proof.get("goal"):
        lines.append(f"Goal: {proof['goal']}")
    lines.extend(["", "Criteria:"])
    lines.append(format_bullets(proof.get("criteria", []), indent="  - "))
    lines.extend(["", "Tests:"])
    lines.append(format_bullets(proof.get("tests", []), indent="  - "))
    lines.extend(["", "Files changed:"])
    lines.append(format_bullets(proof.get("files_changed", []), indent="  - "))
    if proof.get("missing"):
        lines.extend(["", "Missing:"])
        lines.append(format_bullets(proof.get("missing", []), indent="  - "))
    if proof.get("evidence"):
        lines.extend(["", "Evidence:", proof["evidence"]])
    return "\n".join(lines).strip()


def format_state(state: Optional[Dict[str, Any]] = None) -> str:
    snapshot = summarize_state(state)
    lines = ["BMad/Symphony state"]
    lines.append(f"Mode: {snapshot['mode']}  Active: {snapshot['active']}")
    if snapshot.get("current_goal"):
        lines.append(f"Current goal: {snapshot['current_goal']}")
    if snapshot.get("context"):
        lines.append(f"Context: {snapshot['context']}")
    if snapshot.get("intake"):
        lines.extend(["", format_intake(snapshot["intake"])])
    if snapshot.get("story"):
        lines.extend(["", format_story(snapshot["story"])])
    if snapshot.get("run"):
        lines.extend(["", format_run_plan(snapshot["run"])])
    if snapshot.get("proof"):
        lines.extend(["", format_proof(snapshot["proof"])])
    if snapshot.get("history"):
        lines.extend(["", "Recent history:"])
        for entry in snapshot["history"][-5:]:
            lines.append(f"  - {entry.get('ts', '')} {entry.get('event', '')}: {entry.get('summary', '')}")
    return "\n".join(lines).strip()


def key_phrase(text: str) -> str:
    return " ".join((text or "").lower().split())


def wants_injection(*, messages: Any = None, conversation_history: Any = None, user_message: Any = None) -> bool:
    haystacks: List[str] = []

    def add(obj: Any) -> None:
        if obj is None:
            return
        if isinstance(obj, str):
            haystacks.append(obj)
            return
        if isinstance(obj, dict):
            for key in ("content", "text", "message"):
                value = obj.get(key)
                if isinstance(value, str) and value:
                    haystacks.append(value)
            return
        if isinstance(obj, Iterable):
            for item in obj:
                add(item)

    add(user_message)
    add(messages)
    add(conversation_history)
    combined = key_phrase("\n".join(haystacks))
    if not combined:
        return False
    return any(token in combined for token in ("bmad", "symphony", "proof gate", "proof-of-work", "proof of work", "launch plan", "implementation run"))


def build_injection(state: Optional[Dict[str, Any]] = None) -> str:
    snapshot = summarize_state(state)
    lines = [
        "BMad/Symphony mode:",
        "1. Intake before build.",
        "2. Create a story with acceptance criteria.",
        "3. Spawn isolated Symphony workers for implementation and verification.",
        "4. Require proof-of-work before handoff.",
    ]
    if snapshot.get("current_goal"):
        lines.append(f"Current goal: {snapshot['current_goal']}")
    if snapshot.get("intake"):
        lines.append(f"Intake: {snapshot['intake'].get('title', '')}")
    if snapshot.get("proof") and snapshot["proof"].get("missing"):
        lines.append("Outstanding proof: " + ", ".join(snapshot["proof"]["missing"]))
    return "\n".join(lines)
