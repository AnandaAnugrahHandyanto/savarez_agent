"""CLI and slash-command wiring for the BMad/Symphony plugin."""

from __future__ import annotations

import argparse
import shlex
from typing import Any, Callable, Optional, Tuple

from . import core


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # type: ignore[override]
        raise ValueError(message)


def _add_common_fields(parser: argparse.ArgumentParser, *, include_goal: bool = True) -> None:
    if include_goal:
        parser.add_argument("--goal", default="", help="Goal or initiative to operate on")
    parser.add_argument("--context", default="", help="Additional context, constraints, or background")


def register_cli(subparser: argparse.ArgumentParser) -> None:
    """Build the ``hermes bmad-symphony`` argparse tree."""
    subs = subparser.add_subparsers(dest="bmad_symphony_command")

    plan_p = subs.add_parser("plan", help="Create a BMad intake and planning brief")
    _add_common_fields(plan_p)
    plan_p.add_argument("--constraints", action="append", default=[], help="Constraint or priority; may be repeated")
    plan_p.add_argument("--repo-scope", default="", help="Optional repository/module scope")
    plan_p.add_argument("--audience", default="agent", help="Audience for the brief (agent, reviewer, user)")

    story_p = subs.add_parser("story", help="Turn the intake into a story with acceptance criteria")
    _add_common_fields(story_p)
    story_p.add_argument("--acceptance", action="append", default=[], help="Acceptance criterion; may be repeated")
    story_p.add_argument("--out-of-scope", action="append", default=[], help="Out-of-scope item; may be repeated")
    story_p.add_argument("--note", action="append", default=[], help="Implementation note; may be repeated")

    run_p = subs.add_parser("run", help="Prepare or dispatch a Symphony execution run")
    _add_common_fields(run_p)
    run_p.add_argument("--work-item", action="append", default=[], help="Work item goal; may be repeated")
    run_p.add_argument("--parallelism", type=int, default=3, help="Number of worker tasks to prepare")
    run_p.add_argument("--toolset", action="append", default=[], help="Toolset to grant workers; may be repeated")
    run_p.add_argument("--auto-dispatch", action="store_true", help="Dispatch a delegate_task payload immediately")

    proof_p = subs.add_parser("proof", help="Evaluate proof-of-work and merge readiness")
    _add_common_fields(proof_p)
    proof_p.add_argument("--evidence", action="append", default=[], help="Evidence item or summary; may be repeated")
    proof_p.add_argument("--criteria", action="append", default=[], help="Proof criterion; may be repeated")
    proof_p.add_argument("--test", action="append", default=[], help="Test / validation step; may be repeated")
    proof_p.add_argument("--file", action="append", default=[], help="File changed / artifact; may be repeated")
    proof_p.add_argument("--notes", default="", help="Reviewer notes or risk notes")

    subs.add_parser("status", help="Show the current BMad/Symphony state")
    subs.add_parser("reset", help="Clear the current BMad/Symphony state")

    subparser.set_defaults(func=handle_cli)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="hermes bmad-symphony", add_help=True)
    register_cli(parser)
    return parser


def _coerce_work_items(args: argparse.Namespace) -> list[str]:
    items = list(getattr(args, "work_item", []) or [])
    return [item for item in items if isinstance(item, str) and item.strip()]


def _emit(message: str, emit: str) -> str:
    if emit == "print":
        print(message)
    return message


def dispatch_namespace(
    args: argparse.Namespace,
    *,
    dispatcher: Optional[Callable[[str, dict], Any]] = None,
    emit: str = "print",
) -> Tuple[int, str]:
    sub = getattr(args, "bmad_symphony_command", None)
    if not sub:
        return 2, _emit("usage: hermes bmad-symphony {plan,story,run,proof,status,reset}", emit)

    if sub == "plan":
        plan = core.build_intake(
            goal=args.goal,
            context=args.context,
            constraints=args.constraints,
            repo_scope=args.repo_scope,
            audience=args.audience,
        )
        state = core.update_state(
            mode="plan",
            goal=args.goal,
            context=args.context,
            intake=plan,
            active=True,
            event="bmad_symphony_plan",
            summary=plan["next_action"],
        )
        return 0, _emit(core.format_intake(plan) + "\n\n" + core.format_state(state), emit)

    if sub == "story":
        story = core.build_story(
            goal=args.goal or core.current_goal(),
            context=args.context,
            acceptance=args.acceptance,
            out_of_scope=args.out_of_scope,
            implementation_notes=args.note,
        )
        state = core.update_state(
            mode="story",
            goal=args.goal or core.current_goal(),
            context=args.context,
            story=story,
            active=True,
            event="bmad_symphony_story",
            summary="Story captured with acceptance criteria",
        )
        return 0, _emit(core.format_story(story) + "\n\n" + core.format_state(state), emit)

    if sub == "run":
        run = core.build_run_plan(
            goal=args.goal or core.current_goal(),
            context=args.context,
            work_items=_coerce_work_items(args),
            parallelism=args.parallelism,
            toolsets=args.toolset,
            auto_dispatch=args.auto_dispatch,
        )
        state = core.update_state(
            mode="run",
            goal=args.goal or core.current_goal(),
            context=args.context,
            run=run,
            active=True,
            event="bmad_symphony_run",
            summary=f"Prepared {len(run['tasks'])} worker task(s)",
        )
        message = core.format_run_plan(run)
        if args.auto_dispatch and dispatcher is not None:
            dispatched = dispatcher("delegate_task", run["recommended_delegate_payload"])
            message += "\n\nDelegate result:\n" + str(dispatched)
        message += "\n\n" + core.format_state(state)
        return 0, _emit(message, emit)

    if sub == "proof":
        proof = core.evaluate_proof(
            goal=args.goal or core.current_goal(),
            evidence=args.evidence,
            criteria=args.criteria,
            tests=args.test,
            files_changed=args.file,
            notes=args.notes,
        )
        state = core.update_state(
            mode="proof",
            goal=args.goal or core.current_goal(),
            proof=proof,
            active=proof["status"] != "pass",
            event="bmad_symphony_proof",
            summary=f"Proof gate evaluated: {proof['status']}",
        )
        return 0, _emit(core.format_proof(proof) + "\n\n" + core.format_state(state), emit)

    if sub == "status":
        return 0, _emit(core.format_state(), emit)

    if sub == "reset":
        state = core.clear_state()
        return 0, _emit("BMad/Symphony state reset.\n\n" + core.format_state(state), emit)

    return 2, _emit(f"unknown subcommand: {sub}", emit)


def handle_cli(args: argparse.Namespace) -> int:
    code, _ = dispatch_namespace(args, dispatcher=None, emit="print")
    return code


def parse_slash(raw_args: str) -> argparse.Namespace:
    parser = build_parser()
    argv = shlex.split(raw_args or "")
    if not argv:
        raise ValueError("No arguments provided")
    return parser.parse_args(argv)


def handle_slash(raw_args: str, *, dispatcher: Optional[Callable[[str, dict], Any]] = None) -> str:
    parser = build_parser()
    argv = shlex.split(raw_args or "")
    if not argv:
        return "usage: /bmad-symphony {plan,story,run,proof,status,reset}"
    try:
        args = parser.parse_args(argv)
    except Exception as exc:
        return f"{exc}\n\nusage: /bmad-symphony {{plan,story,run,proof,status,reset}}"
    _, message = dispatch_namespace(args, dispatcher=dispatcher, emit="text")
    return message
