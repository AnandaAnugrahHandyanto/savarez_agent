"""CLI and slash command handling for Janitor."""

from __future__ import annotations

import argparse
import json
from typing import Any

from . import core


def build_parser(parser: argparse.ArgumentParser | None = None) -> argparse.ArgumentParser:
    parser = parser or argparse.ArgumentParser(prog="hermes janitor", description="Run Janitor cleanup workflows")
    sub = parser.add_subparsers(dest="action")

    start = sub.add_parser("start", aliases=["janitor"], help="start senior-engineer slop-code cleanup")
    start.add_argument("goal", nargs="*", help="cleanup goal")
    start.add_argument("--goal", dest="goal_opt", help="cleanup goal")
    start.add_argument("--path", "--codebase-path", dest="codebase_path", default="")
    start.add_argument("--symptoms", action="append", default=[])
    start.add_argument("--constraints", action="append", default=[])
    start.add_argument("--rewrite-policy", default="first-principles-when-needed")

    review = sub.add_parser("review", help="apply the senior-engineer janitor scorecard")
    review.add_argument("notes", nargs="*", help="review notes or plan summary")
    review.add_argument("--evidence", action="append", default=[])
    review.add_argument("--notes", dest="notes_opt", help="review notes or plan summary")

    story = sub.add_parser("story", help="add a story")
    story.add_argument("title", nargs="*", help="story title")
    story.add_argument("--title", dest="title_opt", help="story title")
    story.add_argument("--acceptance", action="append", default=[])
    story.add_argument("--notes", default="")
    story.add_argument("--priority", default="normal")

    run = sub.add_parser("run", help="prepare execution handoffs")
    run.add_argument("--parallelism", type=int, default=1)
    run.add_argument("--story-ids", default="")

    proof = sub.add_parser("proof", help="record proof evidence")
    proof.add_argument("--evidence", action="append", default=[])
    proof.add_argument("--test", "--tests", dest="tests", action="append", default=[])
    proof.add_argument("--file", "--files", dest="files", action="append", default=[])
    proof.add_argument("--story-id", default="")

    daily = sub.add_parser("daily-prompt", help="print the daily GitHub Janitor cron prompt")
    daily.add_argument("--owner", default="crisweber2600")
    daily.add_argument("--lookback-hours", type=int, default=24)
    daily.add_argument("--schedule", default="0 9 * * *")

    sub.add_parser("status", help="show status")
    sub.add_parser("reset", help="reset state")
    return parser


def dispatch_namespace(args: argparse.Namespace, *, emit: str = "print") -> tuple[int, str]:
    action = args.action or "status"
    if action in {"start", "janitor"}:
        goal = args.goal_opt or " ".join(args.goal)
        result = core.janitor(
            goal=goal,
            codebase_path=args.codebase_path,
            symptoms=args.symptoms,
            constraints=args.constraints,
            rewrite_policy=args.rewrite_policy,
        )
    elif action == "review":
        notes = args.notes_opt or " ".join(args.notes)
        result = core.janitor_review(evidence=args.evidence, notes=notes)
    elif action == "story":
        title = args.title_opt or " ".join(args.title)
        result = core.add_story(title=title, acceptance=args.acceptance, notes=args.notes, priority=args.priority)
    elif action == "run":
        result = core.prepare_run(parallelism=args.parallelism, story_ids=args.story_ids)
    elif action == "proof":
        result = core.record_proof(evidence=args.evidence, tests=args.tests, files=args.files, story_id=args.story_id)
    elif action == "daily-prompt":
        result = core.daily_prompt(owner=args.owner, lookback_hours=args.lookback_hours, schedule=args.schedule)
    elif action == "reset":
        result = core.reset()
    else:
        result = core.status()

    if action == "status":
        text = core.format_status(result)
    else:
        text = json.dumps(result, ensure_ascii=False, indent=2)
    if emit == "print":
        print(text)
    return (0 if result.get("ok") else 1), text


def register_cli(parser) -> None:
    build_parser(parser)


def handle_slash(raw_args: str) -> str:
    action, args = core.parse_slash(raw_args)
    if action in {"status", ""}:
        return core.format_status(core.status())
    if action in {"start", "janitor"}:
        result = core.janitor(
            goal=args.get("goal") or args.get("text") or "",
            codebase_path=args.get("path") or args.get("codebase_path") or "",
            symptoms=args.get("symptoms", ""),
            constraints=args.get("constraints", ""),
            rewrite_policy=args.get("rewrite_policy", "first-principles-when-needed"),
        )
    elif action == "review":
        result = core.janitor_review(evidence=args.get("evidence", ""), notes=args.get("notes") or args.get("text") or "")
    elif action == "story":
        title = args.get("title") or args.get("text") or ""
        result = core.add_story(title=title, acceptance=args.get("acceptance", ""), notes=args.get("notes", ""), priority=args.get("priority", "normal"))
    elif action == "run":
        result = core.prepare_run(parallelism=args.get("parallelism", 1), story_ids=args.get("story_ids", ""))
    elif action == "proof":
        result = core.record_proof(evidence=args.get("evidence", ""), tests=args.get("test") or args.get("tests") or "", files=args.get("file") or args.get("files") or "", story_id=args.get("story_id", ""))
    elif action == "daily-prompt":
        result = core.daily_prompt(owner=args.get("owner", "crisweber2600"), lookback_hours=args.get("lookback_hours", 24), schedule=args.get("schedule", "0 9 * * *"))
    elif action == "reset":
        result = core.reset()
    else:
        return "Unknown Janitor action. Use: /janitor start|review|story|run|proof|status|reset|daily-prompt"
    return json.dumps(result, ensure_ascii=False, indent=2)
