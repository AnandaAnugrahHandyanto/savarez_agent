"""Tool handlers for the BMad/Symphony plugin."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

from . import core


def _json(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _maybe_dispatch_delegate(
    ctx: Any,
    payload: Dict[str, Any],
) -> Optional[Any]:
    if ctx is None:
        return None
    dispatcher = getattr(ctx, "dispatch_tool", None)
    if not callable(dispatcher):
        return None
    try:
        return dispatcher("delegate_task", payload)
    except Exception:
        return None


def build_tool_handlers(ctx: Any) -> Dict[str, Callable[..., str]]:
    """Return closure-based tool handlers bound to an optional plugin context."""

    def bmad_intake(*, goal: str, context: str = "", constraints: Any = None, repo_scope: str = "", audience: str = "agent", **_: Any) -> str:
        plan = core.build_intake(
            goal=goal,
            context=context,
            constraints=constraints,
            repo_scope=repo_scope,
            audience=audience,
        )
        state = core.update_state(
            mode="plan",
            goal=goal,
            context=context,
            intake=plan,
            active=True,
            event="bmad_intake",
            summary=plan["next_action"],
        )
        return _json({"plan": plan, "state": core.summarize_state(state)})

    def bmad_story(*, goal: str = "", context: str = "", acceptance: Any = None, out_of_scope: Any = None, implementation_notes: Any = None, **_: Any) -> str:
        current = goal or core.current_goal()
        story = core.build_story(
            goal=current,
            context=context,
            acceptance=acceptance,
            out_of_scope=out_of_scope,
            implementation_notes=implementation_notes,
        )
        state = core.update_state(
            mode="story",
            goal=current,
            context=context,
            story=story,
            active=True,
            event="bmad_story",
            summary="Story captured with acceptance criteria",
        )
        return _json({"story": story, "state": core.summarize_state(state)})

    def symphony_run(
        *,
        goal: str = "",
        context: str = "",
        work_items: Any = None,
        parallelism: int = 3,
        toolsets: Any = None,
        auto_dispatch: bool = False,
        **_: Any,
    ) -> str:
        current = goal or core.current_goal()
        run = core.build_run_plan(
            goal=current,
            context=context,
            work_items=work_items,
            parallelism=parallelism,
            toolsets=toolsets,
            auto_dispatch=auto_dispatch,
        )
        state = core.update_state(
            mode="run",
            goal=current,
            context=context,
            run=run,
            active=True,
            event="symphony_run",
            summary=f"Prepared {len(run['tasks'])} Symphony worker task(s)",
        )
        dispatched = None
        if auto_dispatch:
            dispatched = _maybe_dispatch_delegate(ctx, run["recommended_delegate_payload"])
        result = {"run": run, "state": core.summarize_state(state)}
        if dispatched is not None:
            result["delegate_result"] = dispatched
        return _json(result)

    def bmad_proof(
        *,
        goal: str = "",
        evidence: Any = None,
        criteria: Any = None,
        tests: Any = None,
        files_changed: Any = None,
        notes: str = "",
        **_: Any,
    ) -> str:
        current = goal or core.current_goal()
        proof = core.evaluate_proof(
            goal=current,
            evidence=evidence,
            criteria=criteria,
            tests=tests,
            files_changed=files_changed,
            notes=notes,
        )
        state = core.update_state(
            mode="proof",
            goal=current,
            proof=proof,
            active=proof["status"] != "pass",
            event="bmad_proof",
            summary=f"Proof gate evaluated: {proof['status']}",
        )
        return _json({"proof": proof, "state": core.summarize_state(state)})

    def bmad_status(**_: Any) -> str:
        return _json(core.summarize_state())

    def bmad_reset(**_: Any) -> str:
        state = core.clear_state()
        return _json({"status": "reset", "state": core.summarize_state(state)})

    return {
        "bmad_intake": bmad_intake,
        "bmad_story": bmad_story,
        "symphony_run": symphony_run,
        "bmad_proof": bmad_proof,
        "bmad_status": bmad_status,
        "bmad_reset": bmad_reset,
    }


def register_toolset(ctx: Any) -> None:
    handlers = build_tool_handlers(ctx)
    schemas: Dict[str, Dict[str, Any]] = {
        "bmad_intake": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "The requested outcome or project goal."},
                "context": {"type": "string", "description": "Constraints, repo context, or background."},
                "constraints": {"type": ["array", "string"], "description": "Optional constraints or priorities."},
                "repo_scope": {"type": "string", "description": "Optional repository / module scope."},
                "audience": {"type": "string", "description": "Who the plan is for (agent, reviewer, user)."},
            },
            "required": ["goal"],
        },
        "bmad_story": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "context": {"type": "string"},
                "acceptance": {"type": ["array", "string"]},
                "out_of_scope": {"type": ["array", "string"]},
                "implementation_notes": {"type": ["array", "string"]},
            },
            "required": [],
        },
        "symphony_run": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "context": {"type": "string"},
                "work_items": {"type": ["array", "string"]},
                "parallelism": {"type": "integer", "minimum": 1},
                "toolsets": {"type": ["array", "string"]},
                "auto_dispatch": {"type": "boolean"},
            },
            "required": [],
        },
        "bmad_proof": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "evidence": {"type": ["array", "string"]},
                "criteria": {"type": ["array", "string"]},
                "tests": {"type": ["array", "string"]},
                "files_changed": {"type": ["array", "string"]},
                "notes": {"type": "string"},
            },
            "required": [],
        },
        "bmad_status": {"type": "object", "properties": {}, "required": []},
        "bmad_reset": {"type": "object", "properties": {}, "required": []},
    }

    for name, handler in handlers.items():
        ctx.register_tool(
            name=name,
            toolset="bmad_symphony",
            schema=schemas[name],
            handler=lambda args, _handler=handler, **kwargs: _handler(**(args or {})),
            description={
                "bmad_intake": "Create a source-grounded BMAD track/phase/workflow intake.",
                "bmad_story": "Turn the intake into a source-grounded BMAD handoff or story.",
                "symphony_run": "Build or dispatch optional Hermes delegation while separating wrapper behavior from BMAD claims.",
                "bmad_proof": "Evaluate whether BMAD guidance is derived from the extracted source model and user context.",
                "bmad_status": "Summarize the current BMAD/Hermes-wrapper state.",
                "bmad_reset": "Clear the active workflow state.",
            }[name],
            emoji={
                "bmad_intake": "🧭",
                "bmad_story": "📘",
                "symphony_run": "🎼",
                "bmad_proof": "✅",
                "bmad_status": "📊",
                "bmad_reset": "🧹",
            }[name],
        )
