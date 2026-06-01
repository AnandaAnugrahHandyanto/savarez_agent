"""Learning / tutoring tools — Jane's structured surface over ``learning.db``.

This is how Jane creates and drives learning topics **from conversation**:
when the user says "help me learn Python tomorrow" or "quiz me on mortgages
every Sunday", Jane calls the ``learning`` tool to create a topic, optionally
schedule recurring lessons/quizzes (as ordinary cron jobs), teach bite-sized
lessons, generate quiz cards, grade answers, and track weak spots.

The tool is a single multiplexed surface (``action=...``) to keep schema /
context small — same shape as :mod:`tools.cronjob_tools`. State lives in
:mod:`hermes_cli.learning_db`; scheduling reuses :func:`cron.jobs.create_job`
(no new scheduler). Humans manage learning via ``hermes learning …`` (CLI) and
the dashboard Learning page — both bypass the agent.

Availability mirrors the cronjob tool: present in interactive CLI and
gateway/messaging sessions (so Jane sees it mid-conversation) and inside the
gateway-ticked cron runs that deliver scheduled lessons.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

from hermes_cli import learning_db as L
from tools.registry import registry, tool_error, tool_result

# Skill that teaches Jane the tutoring pedagogy inside scheduled runs.
TUTOR_SKILL = "learning-tutor"
# Toolsets a scheduled learning run needs: the learning tool + light research.
LEARNING_JOB_TOOLSETS = ["learning", "web"]
# Scheduled lessons/quizzes are delivered to the Telegram home channel.
LEARNING_DELIVER = "telegram"

VALID_MODES = ("lesson", "quiz", "reminder")


# ---------------------------------------------------------------------------
# Origin capture (which chat created the topic) — mirrors cronjob_tools
# ---------------------------------------------------------------------------


def _origin_from_env() -> Optional[Dict[str, Any]]:
    try:
        from gateway.session_context import get_session_env

        platform = get_session_env("HERMES_SESSION_PLATFORM")
        chat_id = get_session_env("HERMES_SESSION_CHAT_ID")
        if platform and chat_id:
            return {
                "platform": platform,
                "chat_id": chat_id,
                "chat_name": get_session_env("HERMES_SESSION_CHAT_NAME") or None,
                "thread_id": get_session_env("HERMES_SESSION_THREAD_ID") or None,
            }
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Cron prompt construction (lesson vs quiz vs reminder)
# ---------------------------------------------------------------------------


def _job_prompt(topic: L.Topic, mode: str) -> str:
    """Build the self-contained prompt a scheduled learning run executes.

    The difference between a reminder, a lesson, and a quiz is entirely the
    prompt — they all reuse the same cron + tutor-skill machinery.
    """
    tid = topic.id
    title = topic.title
    if mode == "reminder":
        return (
            f"Scheduled learning reminder for the topic '{title}'. "
            f"Send the user one short, warm nudge to spend a few minutes on "
            f"'{title}' today. One or two sentences. Do not teach a full lesson."
        )
    if mode == "quiz":
        return (
            f"Scheduled QUIZ for the learning topic '{title}' (topic_id={tid}). "
            f"Use the `learning` tool: call action='due_cards' with topic_id='{tid}' "
            f"to get the cards to review (weakest first). Ask the user each question, "
            f"wait for their answer, then call action='grade' with the card_id and a "
            f"0-5 grade (0=blank, 3=correct-with-effort, 5=instant). After the set, "
            f"give a short recap that NAMES what they missed and what to review next. "
            f"If there are no due cards, say so briefly and offer the next lesson instead."
        )
    # default: lesson
    return (
        f"Scheduled LESSON for the learning topic '{title}' (topic_id={tid}). "
        f"Use the `learning` tool: call action='next_lesson' with topic_id='{tid}'. "
        f"If a planned lesson is returned, teach it in ONE bite-sized piece (a single "
        f"concept, end with a 1-2 sentence recap), then call action='mark_taught' with "
        f"its lesson_id, then call action='add_cards' to add 2-4 quiz cards drawn from "
        f"what you just taught. If no planned lesson exists yet, decide the next logical "
        f"lesson for '{title}', call action='add_lesson' (status='planned') to record it, "
        f"then teach it the same way."
    )


def _schedule_topic_job(
    topic: L.Topic, *, schedule: str, mode: str, repeat: Optional[int]
) -> Dict[str, Any]:
    """Create a cron job that delivers scheduled lessons/quizzes for a topic."""
    from cron.jobs import create_job

    name = f"Learning: {topic.title} ({mode})"
    job = create_job(
        prompt=_job_prompt(topic, mode),
        schedule=schedule,
        name=name,
        repeat=repeat,
        deliver=LEARNING_DELIVER,
        origin=topic.origin or _origin_from_env(),
        skills=[TUTOR_SKILL],
        enabled_toolsets=list(LEARNING_JOB_TOOLSETS),
    )
    return job


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _topic_brief(t: L.Topic) -> Dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "status": t.status,
        "cadence": t.cadence,
        "level": t.level,
        "cron_job_id": t.cron_job_id,
    }


# ---------------------------------------------------------------------------
# Main tool
# ---------------------------------------------------------------------------


def learning(action: str, **kw: Any) -> str:
    """Unified learning/tutoring tool. See LEARNING_SCHEMA for actions."""
    act = (action or "").strip().lower()
    try:
        with L.connect_closing() as conn:
            # -- topic lifecycle -------------------------------------------------
            if act in ("create_topic", "create", "new_topic"):
                title = (kw.get("title") or "").strip()
                if not title:
                    return tool_error("title is required to create a topic", success=False)
                existing = L.find_topic_by_title(conn, title)
                if existing:
                    topic = existing
                    created = False
                else:
                    tid = L.create_topic(
                        conn,
                        title=title,
                        goal=kw.get("goal"),
                        level=kw.get("level"),
                        cadence=kw.get("cadence"),
                        origin=_origin_from_env(),
                    )
                    topic = L.get_topic(conn, tid)
                    created = True

                job_info = None
                schedule = kw.get("schedule")
                if schedule:
                    mode = (kw.get("mode") or "lesson").strip().lower()
                    if mode not in VALID_MODES:
                        return tool_error(
                            f"mode must be one of {VALID_MODES}", success=False
                        )
                    try:
                        job = _schedule_topic_job(
                            topic, schedule=schedule, mode=mode, repeat=kw.get("repeat")
                        )
                    except Exception as e:  # schedule parse / cron errors
                        return tool_error(f"could not schedule topic: {e}", success=False)
                    L.update_topic(
                        conn,
                        topic.id,
                        {"cron_job_id": job["id"], "cadence": kw.get("cadence") or schedule},
                    )
                    job_info = {
                        "job_id": job["id"],
                        "schedule": job.get("schedule_display"),
                        "mode": mode,
                        "next_run_at": job.get("next_run_at"),
                        "deliver": job.get("deliver"),
                    }
                    topic = L.get_topic(conn, topic.id)

                return tool_result(
                    {
                        "created": created,
                        "topic": _topic_brief(topic),
                        "scheduled": job_info,
                        "message": (
                            f"Topic '{topic.title}' "
                            + ("created" if created else "already existed")
                            + (
                                f"; scheduled {job_info['mode']} on {job_info['schedule']}."
                                if job_info
                                else "."
                            )
                        ),
                    }
                )

            if act in ("list_topics", "list"):
                topics = L.list_topics(
                    conn, include_archived=bool(kw.get("include_archived"))
                )
                return tool_result(
                    {"count": len(topics), "topics": [_topic_brief(t) for t in topics]}
                )

            if act in ("show_topic", "show"):
                topic = _require_topic(conn, kw.get("topic_id"))
                if isinstance(topic, str):
                    return topic
                lessons = L.list_lessons(conn, topic.id)
                weak = L.weak_spots(conn, topic.id, limit=20)
                return tool_result(
                    {
                        "topic": topic.to_dict(),
                        "progress": L.topic_progress(conn, topic.id),
                        "lessons": [
                            {"id": ls.id, "seq": ls.seq, "title": ls.title,
                             "status": ls.status}
                            for ls in lessons
                        ],
                        "weak_spots": [
                            {"id": c.id, "question": c.question, "lapses": c.lapses}
                            for c in weak
                        ],
                    }
                )

            if act in ("update_topic", "update"):
                topic = _require_topic(conn, kw.get("topic_id"))
                if isinstance(topic, str):
                    return topic
                updates = {
                    k: kw[k]
                    for k in ("title", "goal", "status", "level", "cadence")
                    if k in kw and kw[k] is not None
                }
                updated = L.update_topic(conn, topic.id, updates)
                return tool_result({"topic": _topic_brief(updated)})

            if act == "schedule":
                topic = _require_topic(conn, kw.get("topic_id"))
                if isinstance(topic, str):
                    return topic
                schedule = kw.get("schedule")
                if not schedule:
                    return tool_error("schedule is required", success=False)
                mode = (kw.get("mode") or "lesson").strip().lower()
                if mode not in VALID_MODES:
                    return tool_error(f"mode must be one of {VALID_MODES}", success=False)
                # Replace any existing schedule for this topic.
                if topic.cron_job_id:
                    try:
                        from cron.jobs import remove_job

                        remove_job(topic.cron_job_id)
                    except Exception:
                        pass
                try:
                    job = _schedule_topic_job(
                        topic, schedule=schedule, mode=mode, repeat=kw.get("repeat")
                    )
                except Exception as e:
                    return tool_error(f"could not schedule topic: {e}", success=False)
                L.update_topic(
                    conn, topic.id, {"cron_job_id": job["id"], "cadence": schedule}
                )
                return tool_result(
                    {
                        "topic_id": topic.id,
                        "job_id": job["id"],
                        "mode": mode,
                        "schedule": job.get("schedule_display"),
                        "next_run_at": job.get("next_run_at"),
                        "message": f"Scheduled {mode} for '{topic.title}'.",
                    }
                )

            # -- lessons ---------------------------------------------------------
            if act == "add_lesson":
                topic = _require_topic(conn, kw.get("topic_id"))
                if isinstance(topic, str):
                    return topic
                lid = L.add_lesson(
                    conn,
                    topic_id=topic.id,
                    title=kw.get("title"),
                    summary=kw.get("summary"),
                    status=(kw.get("status") or "planned"),
                )
                return tool_result({"lesson_id": lid, "topic_id": topic.id})

            if act == "next_lesson":
                topic = _require_topic(conn, kw.get("topic_id"))
                if isinstance(topic, str):
                    return topic
                lesson = L.next_planned_lesson(conn, topic.id)
                if lesson is None:
                    return tool_result(
                        {
                            "topic_id": topic.id,
                            "lesson": None,
                            "message": "No planned lesson. Decide the next concept, "
                            "call action='add_lesson' to record it, then teach it.",
                        }
                    )
                return tool_result(
                    {
                        "topic_id": topic.id,
                        "lesson": {
                            "id": lesson.id,
                            "seq": lesson.seq,
                            "title": lesson.title,
                            "summary": lesson.summary,
                        },
                    }
                )

            if act in ("mark_taught", "mark_lesson_taught"):
                lesson_id = kw.get("lesson_id")
                if not lesson_id:
                    return tool_error("lesson_id is required", success=False)
                L.mark_lesson_taught(conn, lesson_id, summary=kw.get("summary"))
                return tool_result({"lesson_id": lesson_id, "status": "taught"})

            # -- cards & quizzing ------------------------------------------------
            if act == "add_cards":
                topic = _require_topic(conn, kw.get("topic_id"))
                if isinstance(topic, str):
                    return topic
                cards = kw.get("cards") or []
                if not isinstance(cards, list) or not cards:
                    return tool_error(
                        "cards must be a non-empty list of {question, answer}",
                        success=False,
                    )
                ids = []
                for card in cards:
                    q = (card or {}).get("question")
                    a = (card or {}).get("answer")
                    if not q or not a:
                        return tool_error(
                            "each card needs a 'question' and 'answer'", success=False
                        )
                    ids.append(
                        L.add_card(
                            conn,
                            topic_id=topic.id,
                            question=q,
                            answer=a,
                            lesson_id=kw.get("lesson_id"),
                        )
                    )
                return tool_result({"topic_id": topic.id, "card_ids": ids, "count": len(ids)})

            if act == "due_cards":
                topic = _require_topic(conn, kw.get("topic_id"))
                if isinstance(topic, str):
                    return topic
                limit = int(kw.get("limit") or 10)
                cards = L.due_cards(conn, topic.id, limit=limit)
                return tool_result(
                    {
                        "topic_id": topic.id,
                        "count": len(cards),
                        "cards": [
                            {"id": c.id, "question": c.question, "answer": c.answer,
                             "lapses": c.lapses}
                            for c in cards
                        ],
                    }
                )

            if act == "grade":
                card_id = kw.get("card_id")
                if not card_id:
                    return tool_error("card_id is required", success=False)
                grade = kw.get("grade")
                if grade is None:
                    return tool_error("grade (0-5) is required", success=False)
                try:
                    result = L.record_attempt(
                        conn,
                        card_id=card_id,
                        grade=int(grade),
                        user_answer=kw.get("user_answer"),
                    )
                except KeyError:
                    return tool_error(f"card '{card_id}' not found", success=False)
                return tool_result(result)

            if act == "progress":
                topic = _require_topic(conn, kw.get("topic_id"))
                if isinstance(topic, str):
                    return topic
                return tool_result(L.topic_progress(conn, topic.id))

        return tool_error(f"unknown learning action '{action}'", success=False)
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("learning tool error")
        return tool_error(str(e), success=False)


def _require_topic(conn, topic_id: Optional[str]):
    """Resolve a topic by id; return a tool_error JSON string if missing."""
    if not topic_id:
        return tool_error("topic_id is required for this action", success=False)
    topic = L.get_topic(conn, topic_id)
    if topic is None:
        return tool_error(
            f"topic '{topic_id}' not found. Use action='list_topics' first.",
            success=False,
        )
    return topic


# ---------------------------------------------------------------------------
# Schema & registration
# ---------------------------------------------------------------------------

LEARNING_SCHEMA = {
    "name": "learning",
    "description": """Manage the user's learning/tutoring topics with one compressed tool.

Use this when the user wants to learn, study, be taught, or be quizzed on a subject
("help me learn Python", "quiz me on mortgages every Sunday", "I want to understand AI agents").

Actions:
- create_topic: start (or reuse) a topic. Fields: title (required), goal, level, cadence
  (human label like "every Sunday"), and OPTIONALLY schedule+mode to set up recurring
  delivery. If schedule is given, a cron job is created that delivers to the user on that
  schedule. mode='lesson' teaches the next bite-sized lesson, 'quiz' runs a spaced-repetition
  quiz, 'reminder' just nudges. schedule format: '1d' (one-shot tomorrow), 'every 2d',
  '0 9 * * 0' (Sundays 9am), ISO timestamp.
- list_topics / show_topic (topic_id) / update_topic (topic_id, status=...).
- schedule (topic_id, schedule, mode): add/replace a topic's recurring delivery.
- add_lesson (topic_id, title, summary, status) / next_lesson (topic_id) / mark_taught (lesson_id).
- add_cards (topic_id, cards=[{question, answer}], lesson_id): record quiz cards AFTER teaching.
- due_cards (topic_id): get cards to quiz now (weakest first). grade (card_id, grade 0-5,
  user_answer): record an answer; missed cards (grade<3) resurface sooner (SM-2 spaced repetition).
- progress (topic_id): lessons taught, cards mastered, weak spots, accuracy.

Teaching style: one concept per lesson, end with a short recap, then add 2-4 cards. When
quizzing, grade honestly and explicitly name what the user missed.""",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "create_topic | list_topics | show_topic | update_topic | "
                "schedule | add_lesson | next_lesson | mark_taught | add_cards | "
                "due_cards | grade | progress",
            },
            "topic_id": {"type": "string", "description": "Topic id (required for most actions)."},
            "title": {"type": "string", "description": "Topic title, or lesson title for add_lesson."},
            "goal": {"type": "string", "description": "What the user wants to get out of the topic."},
            "level": {
                "type": "string",
                "description": "Self-reported level: beginner | intermediate | advanced.",
            },
            "cadence": {
                "type": "string",
                "description": "Human cadence label, e.g. 'daily', 'every Sunday'.",
            },
            "schedule": {
                "type": "string",
                "description": "Cron/interval/one-shot schedule for delivery. '1d' = once tomorrow, "
                "'every 2d', '0 9 * * 0' = Sundays 9am, or an ISO timestamp.",
            },
            "mode": {
                "type": "string",
                "description": "For create_topic/schedule: 'lesson' (teach next lesson), "
                "'quiz' (spaced-repetition quiz), or 'reminder' (nudge only). Default 'lesson'.",
            },
            "repeat": {
                "type": "integer",
                "description": "Optional run count (omit = forever for recurring, once for one-shot).",
            },
            "status": {
                "type": "string",
                "description": "Topic status (active|paused|done|archived) or lesson status "
                "(planned|taught|skipped).",
            },
            "include_archived": {
                "type": "boolean",
                "description": "list_topics: include archived topics.",
            },
            "lesson_id": {"type": "string", "description": "Lesson id (mark_taught, add_cards)."},
            "summary": {
                "type": "string",
                "description": "Lesson body / what was taught (add_lesson, mark_taught).",
            },
            "cards": {
                "type": "array",
                "description": "add_cards: list of {question, answer} quiz cards.",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "answer": {"type": "string"},
                    },
                    "required": ["question", "answer"],
                },
            },
            "limit": {"type": "integer", "description": "due_cards: max cards to return (default 10)."},
            "card_id": {"type": "string", "description": "grade: the card being answered."},
            "grade": {
                "type": "integer",
                "description": "grade: 0-5 recall quality. 0=blank, 2=wrong, 3=correct-with-effort, "
                "5=instant. <3 counts as a miss and resurfaces the card sooner.",
            },
            "user_answer": {"type": "string", "description": "grade: what the user answered (logged)."},
        },
        "required": ["action"],
    },
}


def check_learning_requirements() -> bool:
    """Available in interactive CLI and gateway/messaging sessions.

    Mirrors :func:`tools.cronjob_tools.check_cronjob_requirements` — the
    learning store is internal (SQLite + the gateway-ticked cron scheduler),
    so no external dependency is required. Gateway-ticked cron runs inherit
    the gateway session flag, so scheduled lessons can use the tool too.
    """
    from utils import env_var_enabled

    return (
        env_var_enabled("HERMES_INTERACTIVE")
        or env_var_enabled("HERMES_GATEWAY_SESSION")
        or env_var_enabled("HERMES_EXEC_ASK")
    )


registry.register(
    name="learning",
    toolset="learning",
    schema=LEARNING_SCHEMA,
    handler=lambda args, **kw: learning(args.get("action", ""), **{
        k: v for k, v in args.items() if k != "action"
    }),
    check_fn=check_learning_requirements,
    emoji="🎓",
)
