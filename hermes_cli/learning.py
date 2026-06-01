"""``hermes learning`` — human CLI + ``/learning`` slash command.

Humans manage learning topics directly (bypassing the agent), the same way
``hermes kanban`` works. The agent's conversational surface is the ``learning``
tool (see :mod:`tools.learning_tools`); both read/write the same store
(:mod:`hermes_cli.learning_db`).

Subcommands:
    topics [--all]            list topics
    show <id>                 topic detail: progress, lessons, weak spots
    new <title> [...]         create a topic (optionally schedule it)
    progress <id>             progress summary
    lesson <id> [...]         add a planned lesson
    cards <id>               list quiz cards (with due/lapse state)
    due <id>                  list cards due for review now
    weak <id>                 list weak spots (missed cards)
    schedule <id> <sched>     add/replace recurring delivery
    pause/resume/archive <id> change topic status
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Optional

from hermes_cli import learning_db as L


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

_STATUS_ICON = {"active": "●", "paused": "⏸", "done": "✓", "archived": "▢"}


def _fmt_ts(ts: Optional[int]) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")


def _topic_line(t: L.Topic) -> str:
    icon = _STATUS_ICON.get(t.status, "?")
    cadence = f"  ↻ {t.cadence}" if t.cadence else ""
    level = f"  [{t.level}]" if t.level else ""
    return f"{icon} {t.id}  {t.title}{level}{cadence}"


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_topics(args) -> int:
    with L.connect_closing() as conn:
        topics = L.list_topics(conn, include_archived=getattr(args, "all", False))
    if not topics:
        print("No learning topics yet. Create one with: hermes learning new \"<title>\"")
        return 0
    for t in topics:
        print(_topic_line(t))
    return 0


def _cmd_show(args) -> int:
    with L.connect_closing() as conn:
        topic = L.get_topic(conn, args.topic_id)
        if topic is None:
            print(f"No topic with id {args.topic_id!r}", file=sys.stderr)
            return 1
        prog = L.topic_progress(conn, topic.id)
        lessons = L.list_lessons(conn, topic.id)
        weak = L.weak_spots(conn, topic.id)
    print(_topic_line(topic))
    if topic.goal:
        print(f"  goal: {topic.goal}")
    print(
        f"  lessons: {prog['lessons_taught']}/{prog['lessons_total']} taught"
        f"   cards: {prog['cards_total']} ({prog['cards_mastered']} mastered)"
        f"   weak spots: {prog['weak_spots']}"
        + (f"   accuracy: {int(prog['accuracy'] * 100)}%" if prog["accuracy"] is not None else "")
    )
    print(f"  last taught: {_fmt_ts(topic.last_taught_at)}"
          + (f"   cron job: {topic.cron_job_id}" if topic.cron_job_id else ""))
    if lessons:
        print("  Lessons:")
        for ls in lessons:
            mark = "✓" if ls.status == "taught" else "·"
            print(f"    {mark} {ls.seq}. {ls.title or '(untitled)'}")
    if weak:
        print("  Weak spots:")
        for c in weak:
            print(f"    ✗{c.lapses}  {c.question}")
    return 0


def _cmd_new(args) -> int:
    with L.connect_closing() as conn:
        existing = L.find_topic_by_title(conn, args.title)
        if existing:
            print(f"Topic '{existing.title}' already exists: {existing.id}")
            topic = existing
        else:
            tid = L.create_topic(
                conn,
                title=args.title,
                goal=args.goal,
                level=args.level,
                cadence=args.cadence,
            )
            topic = L.get_topic(conn, tid)
            print(f"Created topic '{topic.title}': {topic.id}")
        # Optional scheduling.
        if args.schedule:
            from tools.learning_tools import _schedule_topic_job

            mode = args.mode or "lesson"
            try:
                job = _schedule_topic_job(
                    topic, schedule=args.schedule, mode=mode, repeat=args.repeat
                )
            except Exception as e:
                print(f"  (could not schedule: {e})", file=sys.stderr)
                return 1
            L.update_topic(conn, topic.id, {"cron_job_id": job["id"],
                                            "cadence": args.cadence or args.schedule})
            print(f"  scheduled {mode} on {job.get('schedule_display')} "
                  f"(job {job['id']}, delivers to telegram)")
    return 0


def _cmd_progress(args) -> int:
    with L.connect_closing() as conn:
        if L.get_topic(conn, args.topic_id) is None:
            print(f"No topic with id {args.topic_id!r}", file=sys.stderr)
            return 1
        print(json.dumps(L.topic_progress(conn, args.topic_id), indent=2))
    return 0


def _cmd_lesson(args) -> int:
    with L.connect_closing() as conn:
        if L.get_topic(conn, args.topic_id) is None:
            print(f"No topic with id {args.topic_id!r}", file=sys.stderr)
            return 1
        lid = L.add_lesson(conn, topic_id=args.topic_id, title=args.title,
                           summary=args.summary, status="planned")
        print(f"Added lesson {lid}")
    return 0


def _cmd_cards(args) -> int:
    with L.connect_closing() as conn:
        rows = conn.execute(
            "SELECT * FROM cards WHERE topic_id=? ORDER BY due_at ASC", (args.topic_id,)
        ).fetchall()
    if not rows:
        print("No cards.")
        return 0
    for r in rows:
        c = L.Card.from_row(r)
        print(f"  {c.id}  due {_fmt_ts(c.due_at)}  reps {c.reps}  lapses {c.lapses}  | {c.question}")
    return 0


def _cmd_due(args) -> int:
    with L.connect_closing() as conn:
        cards = L.due_cards(conn, args.topic_id, limit=getattr(args, "limit", 20))
    if not cards:
        print("Nothing due.")
        return 0
    for c in cards:
        print(f"  {c.id}  (lapses {c.lapses})  Q: {c.question}\n      A: {c.answer}")
    return 0


def _cmd_weak(args) -> int:
    with L.connect_closing() as conn:
        cards = L.weak_spots(conn, args.topic_id)
    if not cards:
        print("No weak spots — nice.")
        return 0
    for c in cards:
        print(f"  ✗{c.lapses}  {c.question}")
    return 0


def _cmd_schedule(args) -> int:
    with L.connect_closing() as conn:
        topic = L.get_topic(conn, args.topic_id)
        if topic is None:
            print(f"No topic with id {args.topic_id!r}", file=sys.stderr)
            return 1
        from tools.learning_tools import _schedule_topic_job

        if topic.cron_job_id:
            try:
                from cron.jobs import remove_job

                remove_job(topic.cron_job_id)
            except Exception:
                pass
        mode = args.mode or "lesson"
        try:
            job = _schedule_topic_job(topic, schedule=args.schedule, mode=mode,
                                      repeat=args.repeat)
        except Exception as e:
            print(f"Could not schedule: {e}", file=sys.stderr)
            return 1
        L.update_topic(conn, topic.id, {"cron_job_id": job["id"], "cadence": args.schedule})
        print(f"Scheduled {mode} for '{topic.title}' on {job.get('schedule_display')} "
              f"(job {job['id']})")
    return 0


def _set_status(topic_id: str, status: str) -> int:
    with L.connect_closing() as conn:
        topic = L.get_topic(conn, topic_id)
        if topic is None:
            print(f"No topic with id {topic_id!r}", file=sys.stderr)
            return 1
        # Pause/resume the linked cron job alongside the topic status.
        if topic.cron_job_id:
            try:
                from cron.jobs import pause_job, resume_job, remove_job

                if status == "paused":
                    pause_job(topic.cron_job_id)
                elif status == "active":
                    resume_job(topic.cron_job_id)
                elif status == "archived":
                    remove_job(topic.cron_job_id)
            except Exception:
                pass
        L.update_topic(conn, topic_id, {"status": status})
        print(f"Topic '{topic.title}' → {status}")
    return 0


def _cmd_pause(args) -> int:
    return _set_status(args.topic_id, "paused")


def _cmd_resume(args) -> int:
    return _set_status(args.topic_id, "active")


def _cmd_archive(args) -> int:
    return _set_status(args.topic_id, "archived")


_HANDLERS = {
    "topics": _cmd_topics,
    "list": _cmd_topics,
    "show": _cmd_show,
    "new": _cmd_new,
    "progress": _cmd_progress,
    "lesson": _cmd_lesson,
    "cards": _cmd_cards,
    "due": _cmd_due,
    "weak": _cmd_weak,
    "schedule": _cmd_schedule,
    "pause": _cmd_pause,
    "resume": _cmd_resume,
    "archive": _cmd_archive,
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser(parent_subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Attach the ``learning`` subcommand tree; return the top parser."""
    p = parent_subparsers.add_parser(
        "learning",
        help="Personal learning: topics, lessons, spaced-repetition quizzes",
        description=(
            "Track what you're learning. Topics hold bite-sized lessons and "
            "quiz cards scheduled with SM-2 spaced repetition. Recurring "
            "lessons/quizzes are delivered on a schedule (via cron) to your "
            "Telegram home channel. The agent (Jane) drives the same store "
            "from conversation via the 'learning' tool."
        ),
    )
    sub = p.add_subparsers(dest="learning_action")

    sp = sub.add_parser("topics", help="List topics")
    sp.add_argument("--all", action="store_true", help="Include archived topics")
    sub.add_parser("list", help="Alias for topics").add_argument(
        "--all", action="store_true"
    )

    sp = sub.add_parser("show", help="Show topic detail")
    sp.add_argument("topic_id")

    sp = sub.add_parser("new", help="Create a topic")
    sp.add_argument("title")
    sp.add_argument("--goal")
    sp.add_argument("--level", choices=["beginner", "intermediate", "advanced"])
    sp.add_argument("--cadence", help="Human cadence label, e.g. 'every Sunday'")
    sp.add_argument("--schedule", help="Cron/interval/one-shot schedule to deliver on")
    sp.add_argument("--mode", choices=["lesson", "quiz", "reminder"], default="lesson")
    sp.add_argument("--repeat", type=int)

    sp = sub.add_parser("progress", help="Progress summary")
    sp.add_argument("topic_id")

    sp = sub.add_parser("lesson", help="Add a planned lesson")
    sp.add_argument("topic_id")
    sp.add_argument("--title")
    sp.add_argument("--summary")

    for name, help_ in (("cards", "List all quiz cards"),
                        ("due", "List cards due now"),
                        ("weak", "List weak spots (missed cards)")):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("topic_id")
        if name == "due":
            sp.add_argument("--limit", type=int, default=20)

    sp = sub.add_parser("schedule", help="Add/replace recurring delivery")
    sp.add_argument("topic_id")
    sp.add_argument("schedule", help="'1d', 'every 2d', '0 9 * * 0', or ISO timestamp")
    sp.add_argument("--mode", choices=["lesson", "quiz", "reminder"], default="lesson")
    sp.add_argument("--repeat", type=int)

    for name in ("pause", "resume", "archive"):
        sp = sub.add_parser(name, help=f"Set topic status to {name}")
        sp.add_argument("topic_id")

    return p


def learning_command(args: argparse.Namespace) -> int:
    """Entry point from ``hermes learning …`` argparse dispatch."""
    action = getattr(args, "learning_action", None)
    if not action:
        print("learning: specify a subcommand (topics, show, new, schedule, …). "
              "Try `hermes learning topics`.", file=sys.stderr)
        return 2
    handler = _HANDLERS.get(action)
    if not handler:
        print(f"learning: unknown action {action!r}", file=sys.stderr)
        return 2
    return int(handler(args) or 0)


_SLASH_HELP = """/learning — personal learning topics & spaced-repetition quizzes

  /learning topics [--all]        list topics
  /learning show <id>             topic detail (progress, lessons, weak spots)
  /learning new "<title>" [--schedule '0 9 * * 0' --mode quiz]
  /learning progress <id>
  /learning due <id>              cards due for review
  /learning weak <id>             missed cards
  /learning schedule <id> <sched> [--mode lesson|quiz|reminder]
  /learning pause|resume|archive <id>
"""


def run_slash(rest: str) -> str:
    """Execute a ``/learning …`` string and return captured output."""
    import contextlib
    import io
    import shlex

    tokens = shlex.split(rest) if rest and rest.strip() else []
    if not tokens or tokens[0] in {"help", "--help", "-h", "?"}:
        return _SLASH_HELP

    _wrap = argparse.ArgumentParser(prog="/learning-wrap", add_help=False)
    _wrap.exit_on_error = False  # type: ignore[attr-defined]
    top_sub = _wrap.add_subparsers(dest="_top")
    parser = build_parser(top_sub)
    parser.prog = "/learning"
    parser.exit_on_error = False  # type: ignore[attr-defined]

    buf_out, buf_err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            ns = parser.parse_args(tokens)
            learning_command(ns)
    except SystemExit:
        pass
    except Exception as e:  # pragma: no cover - defensive
        return f"/learning error: {e}"
    out = buf_out.getvalue() + buf_err.getvalue()
    return out.strip() or "(no output)"
