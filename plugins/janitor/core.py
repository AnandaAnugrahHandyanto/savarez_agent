"""Core state machine for the Janitor plugin."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

TRACKS = {"quick", "method", "enterprise", "cleanup"}

SENIOR_ENGINEER_BENCHMARK_SOURCE = {
    "transcript": "Lenny's Podcast with Dan Shipper, 'The AI paradox: More automation, more humans, more work'",
    "article": "Every, 'Vibe Check: GPT-5.5 Has It All'",
    "benchmark_frame": "Rewrite a slop-coded codebase the way a senior engineer would, rather than blindly fixing the reported issue list.",
    "key_observation": "Senior engineers reframe: they inspect the codebase, identify unsalvageable architecture, preserve contracts, and push for a risky-but-necessary rewrite when patches only create more failures.",
}

CLEANUP_RUBRIC = [
    "Diagnose the real failure modes before editing: reproduce symptoms, inspect logs, map data/control flow, and identify root causes.",
    "Preserve product behavior and external contracts unless the story explicitly changes them.",
    "Prefer a senior-engineer rewrite from first principles when the architecture is fundamentally wrong; do not paper over slop with edge patches.",
    "Delete accidental complexity, dead code, duplicated abstractions, and speculative framework glue.",
    "Introduce characterization tests or probes before risky rewrites, then regression tests for the new design.",
    "Keep changes reviewable: stage the rewrite behind clear seams and explain tradeoffs, migrations, and rollback paths.",
    "Require proof stronger than 'it runs': tests, lint/type checks, representative logs/traces, diff review, and residual-risk notes.",
]

CLEANUP_SCORECARD = [
    {
        "name": "frame_control",
        "weight": 20,
        "standard": "Does not obey the narrow bug list blindly; independently decides whether the right job is root-cause cleanup, subsystem rewrite, or targeted patch.",
    },
    {
        "name": "system_understanding",
        "weight": 15,
        "standard": "Maps data flow, lifecycle, failure modes, ownership boundaries, and hidden coupling before changing code.",
    },
    {
        "name": "invariant_preservation",
        "weight": 15,
        "standard": "Captures public API, UX, data, migration, security, and operational invariants with characterization tests/probes.",
    },
    {
        "name": "first_principles_design",
        "weight": 20,
        "standard": "Replaces accidental architecture with a simpler design when warranted; deletes slop instead of wrapping it.",
    },
    {
        "name": "execution_depth",
        "weight": 15,
        "standard": "Carries the rewrite through production-relevant seams, migrations, and call sites instead of stopping at a cosmetic patch.",
    },
    {
        "name": "proof_and_operability",
        "weight": 15,
        "standard": "Proves the cleanup with tests, lint/type checks, logs/traces, load/error-path evidence, rollback notes, and residual-risk review.",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def state_dir() -> Path:
    path = get_hermes_home() / "plugins" / "janitor"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_file() -> Path:
    return state_dir() / "state.json"


def default_state() -> dict[str, Any]:
    return {
        "active": False,
        "track": None,
        "goal": "",
        "constraints": [],
        "phases": [],
        "stories": [],
        "runs": [],
        "proof": [],
        "rubric": [],
        "scorecard": [],
        "specialization": None,
        "created_at": None,
        "updated_at": None,
    }


def load_state() -> dict[str, Any]:
    path = state_file()
    if not path.exists():
        return default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = default_state()
        state.update(data if isinstance(data, dict) else {})
        return state
    except Exception:
        corrupt = path.with_suffix(f".corrupt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
        path.replace(corrupt)
        state = default_state()
        state["warning"] = f"Previous state was unreadable and moved to {corrupt}"
        return state


def save_state(state: dict[str, Any]) -> dict[str, Any]:
    state = dict(state)
    state["updated_at"] = _now()
    state_file().write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return state


def _split_csv(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [part.strip() for part in str(value).replace("\n", ",").split(",") if part.strip()]


def plan(goal: str, track: str = "method", constraints: str | list[str] | None = None) -> dict[str, Any]:
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "goal is required"}
    track = (track or "method").strip().lower()
    if track not in TRACKS:
        return {"ok": False, "error": f"track must be one of {sorted(TRACKS)}"}
    phases = _phases_for(track)
    state = default_state()
    state.update(
        {
            "active": True,
            "track": track,
            "goal": goal,
            "constraints": _split_csv(constraints),
            "phases": phases,
            "created_at": _now(),
        }
    )
    state = save_state(state)
    return {
        "ok": True,
        "state": state,
        "next": "Create acceptance-testable cleanup stories with janitor_story or /janitor story.",
    }


def janitor(
    goal: str,
    codebase_path: str = "",
    symptoms: str | list[str] | None = None,
    constraints: str | list[str] | None = None,
    rewrite_policy: str = "first-principles-when-needed",
) -> dict[str, Any]:
    """Start a senior-engineer cleanup workflow for slop/vibe-coded codebases."""
    goal = (goal or "Clean up a slop-coded codebase to senior-engineer quality").strip()
    state = default_state()
    symptom_list = _split_csv(symptoms)
    constraint_list = _split_csv(constraints)
    path = (codebase_path or "").strip()
    if path:
        constraint_list.insert(0, f"codebase_path={path}")
    if rewrite_policy:
        constraint_list.append(f"rewrite_policy={rewrite_policy.strip()}")
    state.update(
        {
            "active": True,
            "track": "cleanup",
            "goal": goal,
            "constraints": constraint_list,
            "phases": _phases_for("cleanup"),
            "rubric": CLEANUP_RUBRIC,
            "scorecard": CLEANUP_SCORECARD,
            "specialization": "senior-engineer-janitor",
            "diagnosis": {
                "codebase_path": path,
                "symptoms": symptom_list,
                "rewrite_policy": rewrite_policy,
                "benchmark_source": SENIOR_ENGINEER_BENCHMARK_SOURCE,
            },
            "created_at": _now(),
        }
    )
    state = save_state(state)
    return {
        "ok": True,
        "state": state,
        "next": "Run codebase reconnaissance, capture invariants, then create cleanup stories with characterization and regression proof requirements.",
        "rubric": CLEANUP_RUBRIC,
        "scorecard": CLEANUP_SCORECARD,
    }


def janitor_review(evidence: str | list[str] | None = None, notes: str = "") -> dict[str, Any]:
    """Return the senior-engineer cleanup scorecard for reviewing a proposed or completed cleanup."""
    evidence_list = _split_csv(evidence)
    state = load_state()
    scorecard = state.get("scorecard") or CLEANUP_SCORECARD
    review = {
        "source": SENIOR_ENGINEER_BENCHMARK_SOURCE,
        "scorecard": scorecard,
        "evidence": evidence_list,
        "notes": (notes or "").strip(),
        "review_questions": [
            "Did we reframe the problem from reported symptoms to root causes?",
            "What contracts and invariants were captured before risky edits?",
            "Which code or abstractions were deleted rather than patched around?",
            "Where did we rewrite from first principles, and why was that safer than incremental patching?",
            "What proof demonstrates the service is more stable, simpler, and operable than before?",
            "What residual risks, migrations, or rollback paths remain?",
        ],
        "pass_standard": "A cleanup passes only when the evidence addresses every scorecard dimension; missing proof is a blocker, not a caveat.",
    }
    state.setdefault("janitor_reviews", []).append({**review, "created_at": _now()})
    save_state(state)
    return {"ok": True, "review": review, "state": state}


def daily_prompt(owner: str = "crisweber2600", lookback_hours: int = 24, schedule: str = "0 9 * * *") -> dict[str, Any]:
    """Return the self-contained prompt for the daily GitHub Janitor sweep.

    The prompt deliberately treats charge data as the primary filter while
    providing a documented GitHub activity fallback, because ordinary GitHub
    repo APIs expose recent pushes/commits but not always per-repository
    billing charge events to the agent.
    """
    owner = (owner or "crisweber2600").strip()
    try:
        lookback_hours = max(1, int(lookback_hours))
    except Exception:
        lookback_hours = 24
    schedule = (schedule or "0 9 * * *").strip()
    prompt = f"""Run the Janitor workflow for GitHub owner {owner}.

Scope:
- Consider every repository owned by {owner}.
- Target repositories that had charges in the past {lookback_hours} hours. If direct per-repository charge data is unavailable from the authenticated GitHub/account APIs, explicitly say so in the run summary and use repositories with commits, pushes, workflow runs, or other billable-looking activity in the past {lookback_hours} hours as the fallback.

For each target repository:
1. Create or update a local scratch clone. Never mix changes across repositories.
2. Inspect the recent activity that qualified the repository, then run Janitor triage: identify slop-code, brittle abstractions, failing tests, dead code, or small cleanup opportunities.
3. Use strict TDD RED-GREEN-REFACTOR development:
   - RED: write or update a focused failing test/characterization check first and run it to prove it fails for the expected reason.
   - GREEN: make the smallest senior-engineer cleanup that passes the test.
   - REFACTOR: simplify only while tests remain green.
4. If no safe cleanup is found, leave the repository untouched and report why.
5. If changes are made, create a branch named janitor/YYYYMMDD-<short-topic>, commit only that repository's cleanup, push it, and open a pull request.
6. The pull request body must explain what changed, why it was worth doing, why the cleanup is safe, the RED/GREEN/REFACTOR evidence, tests run, and residual risks.

Safety and proof requirements:
- Do not expose secrets. Do not commit generated credentials, local env files, or unrelated files.
- Prefer small reviewable PRs over broad rewrites.
- Run repository-native tests for touched areas and include commands/results in each PR.
- If a repo has existing unrelated dirty state, skip it or isolate a fresh clone.

Final response: list targeted repos, skipped repos and reasons, PR URLs opened, tests run, and any repos where charge data was unavailable and activity fallback was used.
"""
    return {"ok": True, "owner": owner, "lookback_hours": lookback_hours, "schedule": schedule, "prompt": prompt}


def _phases_for(track: str) -> list[dict[str, Any]]:
    if track == "cleanup":
        return [
            {"name": "triage", "required": True, "status": "pending"},
            {"name": "invariants", "required": True, "status": "pending"},
            {"name": "target-architecture", "required": True, "status": "pending"},
            {"name": "cleanup-stories", "required": True, "status": "pending"},
            {"name": "rewrite-or-refactor", "required": True, "status": "pending"},
            {"name": "regression-proof", "required": True, "status": "pending"},
        ]
    if track == "quick":
        return [
            {"name": "tech-spec", "required": True, "status": "pending"},
            {"name": "stories", "required": True, "status": "pending"},
            {"name": "implementation", "required": True, "status": "pending"},
            {"name": "proof", "required": True, "status": "pending"},
        ]
    phases = [
        {"name": "analysis", "required": False, "status": "pending"},
        {"name": "prd", "required": True, "status": "pending"},
        {"name": "architecture", "required": True, "status": "pending"},
        {"name": "stories", "required": True, "status": "pending"},
        {"name": "implementation", "required": True, "status": "pending"},
        {"name": "proof", "required": True, "status": "pending"},
    ]
    if track == "enterprise":
        phases.insert(3, {"name": "security-devops", "required": True, "status": "pending"})
    return phases


def add_story(title: str, acceptance: str | list[str] | None = None, notes: str = "", priority: str = "normal") -> dict[str, Any]:
    title = (title or "").strip()
    if not title:
        return {"ok": False, "error": "title is required"}
    criteria = _split_csv(acceptance)
    if not criteria:
        return {"ok": False, "error": "at least one acceptance criterion is required"}
    state = load_state()
    if not state.get("active"):
        state.update({"active": True, "track": "method", "goal": "Ad-hoc Janitor workflow", "created_at": _now(), "phases": _phases_for("method")})
    story = {
        "id": f"S{len(state.get('stories', [])) + 1}",
        "title": title,
        "acceptance": criteria,
        "notes": (notes or "").strip(),
        "priority": (priority or "normal").strip(),
        "status": "ready",
        "proof": [],
        "created_at": _now(),
    }
    state.setdefault("stories", []).append(story)
    _mark_phase(state, "stories", "in_progress")
    _mark_phase(state, "cleanup-stories", "in_progress")
    save_state(state)
    return {"ok": True, "story": story, "state": state}


def prepare_run(parallelism: int = 1, story_ids: list[str] | str | None = None) -> dict[str, Any]:
    state = load_state()
    stories = state.get("stories", [])
    wanted = set(_split_csv(story_ids))
    selected = [s for s in stories if not wanted or s.get("id") in wanted]
    if not selected:
        return {"ok": False, "error": "no stories available for run"}
    try:
        parallelism = max(1, int(parallelism))
    except Exception:
        parallelism = 1
    handoffs = [_handoff_for(state, s) for s in selected]
    run = {"id": f"R{len(state.get('runs', [])) + 1}", "parallelism": parallelism, "story_ids": [s["id"] for s in selected], "created_at": _now()}
    state.setdefault("runs", []).append(run)
    _mark_phase(state, "implementation", "in_progress")
    _mark_phase(state, "rewrite-or-refactor", "in_progress")
    save_state(state)
    return {"ok": True, "run": run, "handoffs": handoffs, "state": state}


def _handoff_for(state: dict[str, Any], story: dict[str, Any]) -> str:
    criteria = "\n".join(f"- {c}" for c in story.get("acceptance", []))
    base = (
        f"Janitor story {story.get('id')}: {story.get('title')}\n"
        f"Goal: {state.get('goal')}\n"
        f"Track: {state.get('track')}\n"
        f"Acceptance criteria:\n{criteria}\n"
        "Proof required: include files changed, tests/logs/traces inspected, and residual risks."
    )
    if state.get("track") != "cleanup":
        return base
    rubric = "\n".join(f"- {item}" for item in state.get("rubric") or CLEANUP_RUBRIC)
    scorecard = "\n".join(
        f"- {item['name']} ({item['weight']} pts): {item['standard']}"
        for item in (state.get("scorecard") or CLEANUP_SCORECARD)
    )
    diagnosis = state.get("diagnosis") or {}
    symptoms = "\n".join(f"- {item}" for item in diagnosis.get("symptoms", [])) or "- not yet captured"
    return (
        f"{base}\n\n"
        "Senior-engineer janitor discipline:\n"
        f"Symptoms to explain:\n{symptoms}\n"
        f"Rewrite policy: {diagnosis.get('rewrite_policy') or 'first-principles-when-needed'}\n"
        "Cleanup rubric:\n"
        f"{rubric}\n"
        "Senior Engineer Benchmark scorecard:\n"
        f"{scorecard}\n"
        "Do not merely paper over failing edges. If the design is unsalvageable, isolate stable contracts and rewrite the subsystem from first principles with characterization tests first."
    )


def record_proof(evidence: str | list[str] | None = None, tests: str | list[str] | None = None, files: str | list[str] | None = None, story_id: str = "") -> dict[str, Any]:
    evidence_list = _split_csv(evidence)
    test_list = _split_csv(tests)
    file_list = _split_csv(files)
    if not (evidence_list or test_list or file_list):
        return {"ok": False, "error": "proof requires evidence, tests, or files"}
    state = load_state()
    entry = {"story_id": story_id.strip(), "evidence": evidence_list, "tests": test_list, "files": file_list, "created_at": _now()}
    state.setdefault("proof", []).append(entry)
    if entry["story_id"]:
        for story in state.get("stories", []):
            if story.get("id") == entry["story_id"]:
                story.setdefault("proof", []).append(entry)
                story["status"] = "proved"
    if state.get("proof"):
        _mark_phase(state, "proof", "complete")
        _mark_phase(state, "regression-proof", "complete")
    save_state(state)
    return {"ok": True, "proof": entry, "complete": proof_gate(state), "state": state}


def proof_gate(state: dict[str, Any] | None = None) -> bool:
    state = state or load_state()
    stories = state.get("stories", [])
    if stories:
        return all(s.get("proof") for s in stories)
    return bool(state.get("proof"))


def status() -> dict[str, Any]:
    state = load_state()
    return {"ok": True, "state": state, "proof_gate": proof_gate(state), "state_file": str(state_file())}


def reset() -> dict[str, Any]:
    path = state_file()
    if path.exists():
        path.unlink()
    return {"ok": True, "state": default_state()}


def _mark_phase(state: dict[str, Any], name: str, status_value: str) -> None:
    for phase in state.get("phases", []):
        if phase.get("name") == name:
            phase["status"] = status_value


def wants_injection(*, messages: Any = None, conversation_history: Any = None, user_message: Any = None, **_: Any) -> bool:
    text = ""
    for item in (user_message,):
        if isinstance(item, dict):
            text += " " + str(item.get("content", ""))
        elif item is not None:
            text += " " + str(item)
    if not text and messages:
        try:
            last = messages[-1]
            if isinstance(last, dict):
                text = str(last.get("content", ""))
        except Exception:
            pass
    lowered = text.lower()
    return any(
        trigger in lowered
        for trigger in (
            "vibe coded",
            "vibe-coded",
            "slop code",
            "slop-coded",
            "slop coded",
            "slopcode",
            "senior engineer benchmark",
            "senior-engineer benchmark",
            "first principles rewrite",
            "rewrite from first principles",
            "janitor",
        )
    )


def build_injection() -> str:
    return (
        "Janitor plugin is available. For code cleanup, use the Janitor state machine: "
        "janitor_start -> janitor_story -> janitor_run -> janitor_proof -> janitor_status. "
        "For vibe-coded/slop-code cleanup, start with janitor_start or /janitor start: diagnose root causes, preserve contracts, rewrite from first principles when needed, and demand regression proof. "
        "Use janitor_review to apply the Senior Engineer Benchmark scorecard before declaring cleanup success. "
        "Follow strict TDD: RED failing characterization/regression tests, GREEN minimal cleanup, REFACTOR after proof."
    )


def format_status(result: dict[str, Any] | None = None) -> str:
    result = result or status()
    state = result.get("state", {})
    lines = ["Janitor status"]
    lines.append(f"active: {state.get('active')}")
    lines.append(f"track: {state.get('track') or 'none'}")
    lines.append(f"goal: {state.get('goal') or 'none'}")
    lines.append(f"stories: {len(state.get('stories', []))}")
    lines.append(f"runs: {len(state.get('runs', []))}")
    lines.append(f"proof entries: {len(state.get('proof', []))}")
    lines.append(f"proof gate: {'passed' if result.get('proof_gate') else 'pending'}")
    return "\n".join(lines)


def parse_slash(raw_args: str) -> tuple[str, dict[str, Any]]:
    parts = shlex.split(raw_args or "")
    if not parts:
        return "status", {}
    action, rest = parts[0], parts[1:]
    args: dict[str, Any] = {}
    key = None
    positionals = []
    for token in rest:
        if token.startswith("--"):
            key = token[2:].replace("-", "_")
            args.setdefault(key, [])
        elif key:
            args[key].append(token)
            key = None
        else:
            positionals.append(token)
    for k, v in list(args.items()):
        args[k] = " ".join(v) if isinstance(v, list) else v
    if positionals:
        args.setdefault("text", " ".join(positionals))
    return action, args
