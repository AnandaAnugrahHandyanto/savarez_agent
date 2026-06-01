"""SQLite-backed Learning store — Jane's tutoring subsystem.

A deliberately separate subsystem from kanban/cron: it owns the *what the
user is learning* state (topics), the bite-sized lessons taught, the quiz
cards with spaced-repetition scheduling, and an append-only log of quiz
attempts so weak spots can be tracked over time.

The DB lives at ``<root>/learning.db`` where ``<root>`` is the shared
Hermes root (the same root that anchors ``kanban.db``). Scheduling is NOT
done here — recurring lessons / quizzes / reminders are ordinary cron jobs
(see :mod:`cron.jobs`); a topic just stores the linked ``cron_job_id``.

Schema (intentionally small):

* ``topics``   — one subject the user is learning.
* ``lessons``  — ordered bite-sized lessons within a topic.
* ``cards``    — quiz items / flashcards carrying SM-2 scheduling state.
* ``attempts`` — append-only record of every quiz answer ("track what I miss").

Spaced repetition uses the classic SM-2 algorithm (see :func:`sm2_update`):
missed cards (grade < 3) reset to a 1-day interval and increment ``lapses``,
so weak spots fall out naturally as cards with ``lapses > 0`` / low ``ease``.
"""
from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from hermes_time import now as _hermes_now

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAY_SECONDS = 86_400
SM2_MIN_EASE = 1.3
SM2_PASS_GRADE = 3  # grade >= 3 counts as a correct recall

VALID_TOPIC_STATUS = ("active", "paused", "done", "archived")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS topics (
    id             TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    goal           TEXT,
    status         TEXT NOT NULL DEFAULT 'active',
    level          TEXT,
    cadence        TEXT,
    cron_job_id    TEXT,
    origin         TEXT,
    created_at     INTEGER NOT NULL,
    last_taught_at INTEGER,
    next_due_at    INTEGER
);

CREATE TABLE IF NOT EXISTS lessons (
    id         TEXT PRIMARY KEY,
    topic_id   TEXT NOT NULL,
    seq        INTEGER NOT NULL,
    title      TEXT,
    summary    TEXT,
    status     TEXT NOT NULL DEFAULT 'planned',
    taught_at  INTEGER,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lessons_topic ON lessons(topic_id, seq);

CREATE TABLE IF NOT EXISTS cards (
    id            TEXT PRIMARY KEY,
    topic_id      TEXT NOT NULL,
    lesson_id     TEXT,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    ease          REAL NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 0,
    reps          INTEGER NOT NULL DEFAULT 0,
    lapses        INTEGER NOT NULL DEFAULT 0,
    due_at        INTEGER NOT NULL,
    created_at    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cards_topic_due ON cards(topic_id, due_at);

CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id     TEXT NOT NULL,
    topic_id    TEXT NOT NULL,
    grade       INTEGER NOT NULL,
    user_answer TEXT,
    asked_at    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_card ON attempts(card_id, asked_at);
"""

_INITIALIZED_PATHS: set[str] = set()


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Topic:
    id: str
    title: str
    goal: Optional[str]
    status: str
    level: Optional[str]
    cadence: Optional[str]
    cron_job_id: Optional[str]
    origin: Optional[Dict[str, Any]]
    created_at: int
    last_taught_at: Optional[int]
    next_due_at: Optional[int]

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Topic":
        origin = row["origin"]
        try:
            origin = json.loads(origin) if origin else None
        except (ValueError, TypeError):
            origin = None
        return cls(
            id=row["id"],
            title=row["title"],
            goal=row["goal"],
            status=row["status"],
            level=row["level"],
            cadence=row["cadence"],
            cron_job_id=row["cron_job_id"],
            origin=origin,
            created_at=row["created_at"],
            last_taught_at=row["last_taught_at"],
            next_due_at=row["next_due_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        return d


@dataclass
class Lesson:
    id: str
    topic_id: str
    seq: int
    title: Optional[str]
    summary: Optional[str]
    status: str
    taught_at: Optional[int]
    created_at: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Lesson":
        return cls(**{k: row[k] for k in cls.__dataclass_fields__})

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class Card:
    id: str
    topic_id: str
    lesson_id: Optional[str]
    question: str
    answer: str
    ease: float
    interval_days: int
    reps: int
    lapses: int
    due_at: int
    created_at: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Card":
        return cls(**{k: row[k] for k in cls.__dataclass_fields__})

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


# ---------------------------------------------------------------------------
# Paths & connection
# ---------------------------------------------------------------------------


def _now() -> int:
    """Current epoch seconds, honouring Hermes' configured timezone clock."""
    return int(_hermes_now().timestamp())


def learning_db_path() -> Path:
    """Resolve the learning DB path.

    ``HERMES_LEARNING_DB`` pins the file directly (tests / unusual
    deployments); otherwise it sits next to ``kanban.db`` under the shared
    Hermes root so it is consistent across profiles.
    """
    override = os.environ.get("HERMES_LEARNING_DB", "").strip()
    if override:
        return Path(override).expanduser()
    from hermes_constants import get_default_hermes_root

    return get_default_hermes_root() / "learning.db"


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open (and lazily initialize) the learning DB."""
    path = db_path or learning_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    resolved = str(path.resolve())
    if resolved not in _INITIALIZED_PATHS:
        try:
            from hermes_state import apply_wal_with_fallback

            apply_wal_with_fallback(conn, db_label="learning.db")
        except Exception:
            # WAL is an optimization, not a correctness requirement.
            pass
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        _INITIALIZED_PATHS.add(resolved)
    return conn


@contextlib.contextmanager
def connect_closing(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    """Open a learning DB connection and guarantee it is closed on exit.

    Mirrors :func:`hermes_cli.kanban_db.connect_closing` — sqlite3's own
    ``with`` only manages the transaction, not the file descriptor, which
    leaks FDs in long-lived processes (gateway / dashboard).
    """
    conn = connect(db_path=db_path)
    try:
        yield conn
    finally:
        with contextlib.suppress(Exception):
            conn.close()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------


def create_topic(
    conn: sqlite3.Connection,
    *,
    title: str,
    goal: Optional[str] = None,
    level: Optional[str] = None,
    cadence: Optional[str] = None,
    cron_job_id: Optional[str] = None,
    origin: Optional[Dict[str, Any]] = None,
    status: str = "active",
) -> str:
    """Insert a new learning topic and return its id."""
    if not title or not title.strip():
        raise ValueError("topic title is required")
    if status not in VALID_TOPIC_STATUS:
        raise ValueError(f"invalid status {status!r}")
    topic_id = _new_id()
    now = _now()
    conn.execute(
        """INSERT INTO topics
           (id, title, goal, status, level, cadence, cron_job_id, origin, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            topic_id,
            title.strip(),
            (goal or None),
            status,
            (level or None),
            (cadence or None),
            (cron_job_id or None),
            json.dumps(origin) if origin else None,
            now,
        ),
    )
    conn.commit()
    return topic_id


def get_topic(conn: sqlite3.Connection, topic_id: str) -> Optional[Topic]:
    row = conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
    return Topic.from_row(row) if row else None


def find_topic_by_title(conn: sqlite3.Connection, title: str) -> Optional[Topic]:
    """Case-insensitive lookup of an active/paused topic by title.

    Lets Jane say "quiz me on mortgages" and find the existing topic instead
    of creating a duplicate.
    """
    row = conn.execute(
        "SELECT * FROM topics WHERE lower(title)=lower(?) "
        "AND status IN ('active','paused') ORDER BY created_at DESC LIMIT 1",
        (title.strip(),),
    ).fetchone()
    return Topic.from_row(row) if row else None


def list_topics(
    conn: sqlite3.Connection, *, include_archived: bool = False
) -> List[Topic]:
    if include_archived:
        rows = conn.execute("SELECT * FROM topics ORDER BY created_at DESC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM topics WHERE status != 'archived' ORDER BY created_at DESC"
        ).fetchall()
    return [Topic.from_row(r) for r in rows]


def update_topic(
    conn: sqlite3.Connection, topic_id: str, updates: Dict[str, Any]
) -> Optional[Topic]:
    """Patch allowed columns on a topic; returns the updated row."""
    allowed = {
        "title",
        "goal",
        "status",
        "level",
        "cadence",
        "cron_job_id",
        "last_taught_at",
        "next_due_at",
    }
    fields = {k: v for k, v in updates.items() if k in allowed}
    if "status" in fields and fields["status"] not in VALID_TOPIC_STATUS:
        raise ValueError(f"invalid status {fields['status']!r}")
    if "origin" in updates:  # serialize separately
        fields["origin"] = json.dumps(updates["origin"]) if updates["origin"] else None
    if not fields:
        return get_topic(conn, topic_id)
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(
        f"UPDATE topics SET {sets} WHERE id=?", (*fields.values(), topic_id)
    )
    conn.commit()
    return get_topic(conn, topic_id)


# ---------------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------------


def add_lesson(
    conn: sqlite3.Connection,
    *,
    topic_id: str,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    status: str = "planned",
) -> str:
    """Append a lesson to a topic, auto-assigning the next ``seq``."""
    row = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) AS m FROM lessons WHERE topic_id=?",
        (topic_id,),
    ).fetchone()
    seq = int(row["m"]) + 1
    lesson_id = _new_id()
    now = _now()
    taught_at = now if status == "taught" else None
    conn.execute(
        """INSERT INTO lessons (id, topic_id, seq, title, summary, status, taught_at, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (lesson_id, topic_id, seq, title, summary, status, taught_at, now),
    )
    conn.commit()
    return lesson_id


def list_lessons(conn: sqlite3.Connection, topic_id: str) -> List[Lesson]:
    rows = conn.execute(
        "SELECT * FROM lessons WHERE topic_id=? ORDER BY seq ASC", (topic_id,)
    ).fetchall()
    return [Lesson.from_row(r) for r in rows]


def next_planned_lesson(conn: sqlite3.Connection, topic_id: str) -> Optional[Lesson]:
    """The lowest-seq lesson that hasn't been taught yet, if any."""
    row = conn.execute(
        "SELECT * FROM lessons WHERE topic_id=? AND status='planned' "
        "ORDER BY seq ASC LIMIT 1",
        (topic_id,),
    ).fetchone()
    return Lesson.from_row(row) if row else None


def mark_lesson_taught(
    conn: sqlite3.Connection, lesson_id: str, *, summary: Optional[str] = None
) -> None:
    now = _now()
    if summary is not None:
        conn.execute(
            "UPDATE lessons SET status='taught', taught_at=?, summary=? WHERE id=?",
            (now, summary, lesson_id),
        )
    else:
        conn.execute(
            "UPDATE lessons SET status='taught', taught_at=? WHERE id=?",
            (now, lesson_id),
        )
    row = conn.execute(
        "SELECT topic_id FROM lessons WHERE id=?", (lesson_id,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE topics SET last_taught_at=? WHERE id=?", (now, row["topic_id"])
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Cards & spaced repetition
# ---------------------------------------------------------------------------


def add_card(
    conn: sqlite3.Connection,
    *,
    topic_id: str,
    question: str,
    answer: str,
    lesson_id: Optional[str] = None,
) -> str:
    """Create a quiz card, due immediately (interval 0)."""
    if not question or not answer:
        raise ValueError("card question and answer are required")
    card_id = _new_id()
    now = _now()
    conn.execute(
        """INSERT INTO cards (id, topic_id, lesson_id, question, answer, due_at, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (card_id, topic_id, lesson_id, question.strip(), answer.strip(), now, now),
    )
    conn.commit()
    return card_id


def due_cards(
    conn: sqlite3.Connection,
    topic_id: str,
    *,
    now: Optional[int] = None,
    limit: int = 10,
) -> List[Card]:
    """Cards due for review now, weakest first.

    Ordering puts the most-lapsed / lowest-ease cards first so a short quiz
    session targets weak spots before easy material.
    """
    now = _now() if now is None else now
    rows = conn.execute(
        "SELECT * FROM cards WHERE topic_id=? AND due_at<=? "
        "ORDER BY lapses DESC, ease ASC, due_at ASC LIMIT ?",
        (topic_id, now, limit),
    ).fetchall()
    return [Card.from_row(r) for r in rows]


def weak_spots(conn: sqlite3.Connection, topic_id: str, *, limit: int = 20) -> List[Card]:
    """Cards the user has missed at least once, weakest first."""
    rows = conn.execute(
        "SELECT * FROM cards WHERE topic_id=? AND lapses>0 "
        "ORDER BY lapses DESC, ease ASC LIMIT ?",
        (topic_id, limit),
    ).fetchall()
    return [Card.from_row(r) for r in rows]


def get_card(conn: sqlite3.Connection, card_id: str) -> Optional[Card]:
    row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
    return Card.from_row(row) if row else None


def sm2_update(card: Card, grade: int) -> Dict[str, Any]:
    """Compute the next SM-2 scheduling state for ``card`` given ``grade`` (0-5).

    Returns a dict of the new ``ease``, ``interval_days``, ``reps``,
    ``lapses``, and ``due_at`` (epoch seconds). Pure function — no DB I/O —
    so it is trivially unit-testable.

    * grade < 3 (lapse): reps reset to 0, interval back to 1 day, lapses+1.
    * grade >= 3: reps+1; interval grows 1 → 6 → round(prev * ease).
    * ease adjusts by the standard SM-2 formula, floored at 1.3.
    """
    grade = max(0, min(5, int(grade)))
    ease = card.ease
    reps = card.reps
    lapses = card.lapses

    # Standard SM-2 easiness update.
    ease = ease + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    if ease < SM2_MIN_EASE:
        ease = SM2_MIN_EASE

    if grade < SM2_PASS_GRADE:
        reps = 0
        interval = 1
        lapses += 1
    else:
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 6
        else:
            interval = max(1, round(card.interval_days * ease))

    due_at = _now() + interval * DAY_SECONDS
    return {
        "ease": round(ease, 4),
        "interval_days": interval,
        "reps": reps,
        "lapses": lapses,
        "due_at": due_at,
    }


def record_attempt(
    conn: sqlite3.Connection,
    *,
    card_id: str,
    grade: int,
    user_answer: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a quiz attempt and reschedule the card via SM-2.

    Returns the new card scheduling state (incl. ``correct`` and
    ``next_due_at``). Raises ``KeyError`` if the card does not exist.
    """
    card = get_card(conn, card_id)
    if card is None:
        raise KeyError(f"card {card_id!r} not found")
    now = _now()
    conn.execute(
        "INSERT INTO attempts (card_id, topic_id, grade, user_answer, asked_at) "
        "VALUES (?,?,?,?,?)",
        (card_id, card.topic_id, int(grade), user_answer, now),
    )
    new = sm2_update(card, grade)
    conn.execute(
        "UPDATE cards SET ease=?, interval_days=?, reps=?, lapses=?, due_at=? WHERE id=?",
        (
            new["ease"],
            new["interval_days"],
            new["reps"],
            new["lapses"],
            new["due_at"],
            card_id,
        ),
    )
    conn.commit()
    new["correct"] = int(grade) >= SM2_PASS_GRADE
    new["card_id"] = card_id
    return new


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


def topic_progress(conn: sqlite3.Connection, topic_id: str) -> Dict[str, Any]:
    """Aggregate progress for a topic: lesson counts, card mastery, weak spots."""
    lessons_total = conn.execute(
        "SELECT COUNT(*) AS c FROM lessons WHERE topic_id=?", (topic_id,)
    ).fetchone()["c"]
    lessons_taught = conn.execute(
        "SELECT COUNT(*) AS c FROM lessons WHERE topic_id=? AND status='taught'",
        (topic_id,),
    ).fetchone()["c"]
    cards_total = conn.execute(
        "SELECT COUNT(*) AS c FROM cards WHERE topic_id=?", (topic_id,)
    ).fetchone()["c"]
    # "Mastered" = answered correctly enough to push the interval past a week.
    cards_mastered = conn.execute(
        "SELECT COUNT(*) AS c FROM cards WHERE topic_id=? AND interval_days>=7",
        (topic_id,),
    ).fetchone()["c"]
    weak = len(weak_spots(conn, topic_id, limit=1000))
    attempts_total = conn.execute(
        "SELECT COUNT(*) AS c FROM attempts WHERE topic_id=?", (topic_id,)
    ).fetchone()["c"]
    attempts_correct = conn.execute(
        "SELECT COUNT(*) AS c FROM attempts WHERE topic_id=? AND grade>=?",
        (topic_id, SM2_PASS_GRADE),
    ).fetchone()["c"]
    accuracy = (attempts_correct / attempts_total) if attempts_total else None
    return {
        "topic_id": topic_id,
        "lessons_total": lessons_total,
        "lessons_taught": lessons_taught,
        "cards_total": cards_total,
        "cards_mastered": cards_mastered,
        "weak_spots": weak,
        "attempts_total": attempts_total,
        "accuracy": round(accuracy, 3) if accuracy is not None else None,
    }
