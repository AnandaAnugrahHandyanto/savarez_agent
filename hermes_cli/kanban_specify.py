"""Kanban triage specifier — flesh out a one-liner into a real spec.

Used by ``hermes kanban specify [task_id | --all]``. Takes a task that
lives in the Triage column (a rough idea, typically only a title), calls
the auxiliary LLM to produce:

  * A tightened title (optional — only replaces if the model proposes a
    materially different one)
  * A concrete body: goal, proposed approach, acceptance criteria
  * An assignee suggestion drawn from the worker profile roster
  * A list of short, lowercase, hyphenated routing labels

and then flips the task ``triage -> todo`` via
``kanban_db.specify_triage_task``. The dispatcher promotes it to
``ready`` on its next tick (or immediately if there are no open parents).

Design notes
------------

* This module intentionally mirrors ``hermes_cli/goals.py`` — same aux
  client pattern, same "empty config => skip, don't crash" tolerance.
  Keeps the surface area tiny and the failure modes predictable.

* The prompt is a short system + user pair. We ask for JSON with
  ``{title, body, assignee_suggestion, labels}``; if parsing fails,
  we fall back to treating the whole response as the body and leave
  the title untouched. No retry loop — one shot, keep cost bounded.

* The ``assignee_suggestion`` is a *suggestion only*. A downstream
  routing engine may override it. The DB write only fills the
  assignee column when it was previously empty (see
  ``specify_triage_task``).

* ``labels`` are short routing/cost tags (e.g. ``long-running``,
  ``review-only``, ``parallel-fan-out``). A parallel migration is
  adding a dedicated ``labels`` column to ``tasks``; until that
  lands, the DB layer falls back to recording them in the
  ``specified`` event payload so nothing is lost.

* Structured output / JSON mode is not requested explicitly so the
  specifier works on providers that don't implement it. The parse
  is lenient (tolerates markdown code fences around the JSON).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from hermes_cli import kanban_db as kb
from hermes_cli import triage_routing

logger = logging.getLogger(__name__)


_PROFILE_ROSTER = (
    "h2coder",
    "h2architect",
    "h2dispatch",
    "h2librarian",
    "h2reviewer",
    "h2research",
    "h2simple",
    "ruflo-swarm",
)


_SYSTEM_PROMPT = """You are the Kanban triage specifier for the Hermes Agent board.
A user dropped a rough idea into the Triage column. Your job is to turn it
into a concrete, actionable task spec that an autonomous worker can pick up
and execute without further clarification.

Output a single JSON object with exactly four keys:

  {
    "title": "<tightened task title, <= 80 chars, imperative voice>",
    "body":  "<multi-line spec, see structure below>",
    "assignee_suggestion": "<one of the profile names below, or null>",
    "labels": ["<short-tag>", "..."]
  }

The body MUST include these sections, each prefixed with a bold markdown
heading, in this order:

  **Goal** — one sentence, user-facing outcome.
  **Approach** — 2-5 bullets on how a worker should tackle it.
  **Acceptance criteria** — checklist of concrete, verifiable conditions.
  **Out of scope** — short list of things NOT to touch (omit if nothing
      obvious; never invent scope creep).

Worker profile roster (pick the best fit for ``assignee_suggestion``):
  - h2coder        — general code changes, bug fixes, refactors.
  - h2architect    — system design, multi-module redesigns, RFCs.
  - h2dispatch     — coordination, scheduling, dispatcher/board mechanics.
  - h2librarian    — docs, READMEs, comment cleanups, knowledge curation.
  - h2reviewer     — review-only or audit-only inspection passes.
  - h2research     — investigation, write-ups, no-code analysis tasks.
  - h2simple       — small, well-scoped chores a junior worker can finish.
  - ruflo-swarm    — long-running parallel fan-out across many subtasks.

If no profile is a clear fit, set ``assignee_suggestion`` to ``null`` —
do NOT guess. A downstream routing engine may override your suggestion.

Labels are short, lowercase, hyphenated routing/cost tags. Prefer these
when they apply, but free-form tags are fine when none match:

  long-running, autopilot, audit-only, review-only, large,
  parallel-fan-out, est-hours-high

Keep ``labels`` empty (``[]``) rather than inventing tags that don't add
information. 1–5 labels is a healthy range; never exceed 10.

Rules:
  - Keep the tightened title close in meaning to the original idea — do
    NOT invent a different project.
  - If the original idea is already detailed, preserve its substance and
    just reformat into the sections above.
  - Never add invented requirements the user didn't hint at.
  - No preamble, no closing remarks, no code fences around the JSON.
  - Output only the JSON object and nothing else.
"""


_USER_TEMPLATE = """Task id: {task_id}
Current title: {title}
Current body:
{body}
"""


@dataclass
class SpecifyOutcome:
    """Result of specifying a single triage task."""

    task_id: str
    ok: bool
    reason: str = ""
    new_title: Optional[str] = None
    # Best-guess profile name proposed by the LLM. ``None`` when the model
    # declined to commit (the recommended behaviour when no profile is a
    # clear fit). A downstream routing engine may override this.
    assignee_suggestion: Optional[str] = None
    # Short, lowercase, hyphenated routing/cost tags. Empty list when the
    # model produced no usable labels.
    labels: list[str] = field(default_factory=list)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _extract_json_blob(raw: str) -> Optional[dict]:
    """Lenient JSON extraction — tolerates fenced code blocks and
    leading/trailing whitespace. Returns None if nothing parses."""
    if not raw:
        return None
    stripped = _FENCE_RE.sub("", raw.strip())
    # Greedy: find the first `{` and last `}` and try that slice.
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None
    candidate = stripped[first : last + 1]
    try:
        val = json.loads(candidate)
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(val, dict):
        return None
    return val


_LABEL_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Cap on labels per task — guards against runaway model output. Anything
# past this is silently dropped (we don't error: a noisy label list still
# lets the rest of the spec through).
_MAX_LABELS = 10
_MAX_LABEL_LEN = 40


def _normalize_label(raw: object) -> Optional[str]:
    """Coerce a single label to the canonical ``lowercase-hyphenated`` form.

    Accepts mild deviations (uppercase, surrounding whitespace, snake_case,
    spaces) and silently rejects strings that can't be cleaned up. Returning
    ``None`` instead of raising keeps a single bad label from poisoning the
    whole batch.
    """
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip().lower()
    # Convert spaces/underscores to hyphens; collapse repeats.
    cleaned = re.sub(r"[\s_]+", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    if not cleaned or len(cleaned) > _MAX_LABEL_LEN:
        return None
    if not _LABEL_RE.match(cleaned):
        return None
    return cleaned


def _normalize_labels(raw: object) -> list[str]:
    """Coerce the model's ``labels`` field to a clean, de-duplicated list.

    Order is preserved (first occurrence wins). Caps at ``_MAX_LABELS``;
    silently drops non-string entries and labels that fail the lowercase-
    hyphenated regex.
    """
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        norm = _normalize_label(item)
        if norm is None or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
        if len(out) >= _MAX_LABELS:
            break
    return out


def _normalize_assignee_suggestion(raw: object) -> Optional[str]:
    """Validate the model's ``assignee_suggestion`` against the roster.

    Returns the canonical profile name when the suggestion matches a known
    profile (case-insensitive, whitespace-tolerant), or ``None`` otherwise.
    ``None`` is the right default for an off-roster guess — we never want
    to write a bogus profile name into the assignee column.
    """
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip().lower()
    if not cleaned:
        return None
    for name in _PROFILE_ROSTER:
        if cleaned == name.lower():
            return name
    return None


def _profile_author() -> str:
    """Mirror of ``hermes_cli.kanban._profile_author``. Kept local to
    avoid a circular import when kanban.py imports this module."""
    return (
        os.environ.get("HERMES_PROFILE")
        or os.environ.get("USER")
        or "specifier"
    )


def specify_task(
    task_id: str,
    *,
    author: Optional[str] = None,
    timeout: Optional[int] = None,
) -> SpecifyOutcome:
    """Specify a single triage task and promote it to ``todo``.

    Returns an outcome describing what happened. Never raises for expected
    failure modes (task not in triage, no aux client configured, API
    error, malformed response) — those surface via ``ok=False`` so the
    ``--all`` sweep can continue past individual failures.
    """
    with kb.connect() as conn:
        task = kb.get_task(conn, task_id)
    if task is None:
        return SpecifyOutcome(task_id, False, "unknown task id")
    if task.status != "triage":
        return SpecifyOutcome(
            task_id, False, f"task is not in triage (status={task.status!r})"
        )

    try:
        from agent.auxiliary_client import get_auxiliary_extra_body, get_text_auxiliary_client
    except Exception as exc:  # pragma: no cover — import smoke test
        logger.debug("specify: auxiliary client import failed: %s", exc)
        return SpecifyOutcome(task_id, False, "auxiliary client unavailable")

    try:
        client, model = get_text_auxiliary_client("triage_specifier")
    except Exception as exc:
        logger.debug("specify: get_text_auxiliary_client failed: %s", exc)
        return SpecifyOutcome(task_id, False, "auxiliary client unavailable")

    if client is None or not model:
        return SpecifyOutcome(
            task_id, False, "no auxiliary client configured"
        )

    user_msg = _USER_TEMPLATE.format(
        task_id=task.id,
        title=_truncate(task.title or "", 400),
        body=_truncate(task.body or "(no body)", 4000),
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=1500,
            timeout=timeout or 120,
            extra_body=get_auxiliary_extra_body() or None,
        )
    except Exception as exc:
        logger.info(
            "specify: API call failed for %s (%s) — skipping",
            task_id, exc,
        )
        return SpecifyOutcome(
            task_id, False, f"LLM error: {type(exc).__name__}"
        )

    try:
        raw = resp.choices[0].message.content or ""
    except Exception:
        raw = ""

    parsed = _extract_json_blob(raw)

    new_title: Optional[str]
    new_body: Optional[str]
    assignee_suggestion: Optional[str] = None
    labels: list[str] = []
    final_assignee: Optional[str] = None
    if parsed is None:
        # Fall back: treat the whole reply as the body, leave title as-is.
        # Worst case the user edits afterward — still better than stranding
        # the task in triage on a malformed LLM reply. No assignee/labels
        # are inferable from prose, so leave them at their defaults.
        stripped_raw = raw.strip()
        if not stripped_raw:
            return SpecifyOutcome(
                task_id, False, "LLM returned an empty response"
            )
        new_title = None
        new_body = stripped_raw
    else:
        title_val = parsed.get("title")
        body_val = parsed.get("body")
        new_title = (
            title_val.strip()
            if isinstance(title_val, str) and title_val.strip()
            else None
        )
        new_body = (
            body_val if isinstance(body_val, str) and body_val.strip() else None
        )
        if new_body is None and new_title is None:
            return SpecifyOutcome(
                task_id, False, "LLM response missing title and body"
            )
        assignee_suggestion = _normalize_assignee_suggestion(
            parsed.get("assignee_suggestion")
        )
        labels = _normalize_labels(parsed.get("labels"))
        try:
            routing_rules = triage_routing.load_routing_rules()
            final_assignee = triage_routing.route(
                labels, assignee_suggestion, routing_rules
            )
        except (ValueError, OSError) as exc:
            logger.warning(
                "routing failed (%s); falling back to LLM suggestion", exc
            )
            final_assignee = assignee_suggestion

    with kb.connect() as conn:
        ok = kb.specify_triage_task(
            conn,
            task_id,
            title=new_title,
            body=new_body,
            assignee_suggestion=final_assignee,
            labels=labels,
            author=author or _profile_author(),
        )
    if not ok:
        # Race: someone else promoted / archived the task between our
        # read above and the write. Report, don't crash.
        return SpecifyOutcome(
            task_id, False, "task moved out of triage before promotion"
        )
    return SpecifyOutcome(
        task_id,
        True,
        "specified",
        new_title=new_title,
        assignee_suggestion=assignee_suggestion,
        labels=labels,
    )


def list_triage_ids(*, tenant: Optional[str] = None) -> list[str]:
    """Return task ids currently in the triage column.

    ``tenant`` narrows the sweep; ``None`` returns every triage task.
    """
    with kb.connect() as conn:
        tasks = kb.list_tasks(
            conn,
            status="triage",
            tenant=tenant,
            include_archived=False,
        )
    return [t.id for t in tasks]
