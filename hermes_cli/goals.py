"""Persistent session goals — the Ralph loop for Hermes.

A goal is a free-form user objective that stays active across turns. After
each turn completes, a small judge call asks an auxiliary model "is this
goal satisfied by the assistant's last response?". If not, Hermes feeds a
continuation prompt back into the same session and keeps working until the
goal is done, turn budget is exhausted, the user pauses/clears it, or the
user sends a new message (which takes priority and pauses the goal loop).

State is persisted in SessionDB's ``state_meta`` table keyed by
``goal:<session_id>`` so ``/resume`` picks it up.

Design notes / invariants:

- The continuation prompt is just a normal user message appended to the
  session via ``run_conversation``. No system-prompt mutation, no toolset
  swap — prompt caching stays intact.
- Judge failures are fail-OPEN: ``continue``. A broken judge must not wedge
  progress; the turn budget is the backstop.
- When a real user message arrives mid-loop it preempts the continuation
  prompt and also pauses the goal loop for that turn (we still re-judge
  after, so if the user's message happens to complete the goal the judge
  will say ``done``).
- This module has zero hard dependency on ``cli.HermesCLI`` or the gateway
  runner — both wire the same ``GoalManager`` in.

Nothing in this module touches the agent's system prompt or toolset.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Constants & defaults
# ──────────────────────────────────────────────────────────────────────

DEFAULT_MAX_TURNS = 20
DEFAULT_JUDGE_TIMEOUT = 30.0
# Judge output budget. The freeform judge returns a one-line JSON verdict, but
# reasoning models (deepseek-v4, qwq, etc.) burn tokens on hidden reasoning
# before emitting the visible JSON — and the first /goal turn's prompt is
# larger than later turns, which pushes total reply length past tight caps.
# 200 tokens (the original default) reliably truncated the JSON on reasoning
# models, leaving '{"done": true, "reason": "The agent successfully' and
# triggering the auto-pause. 4096 covers reasoning + verdict on every model
# we've live-tested; override via auxiliary.goal_judge.max_tokens for
# specifically constrained setups.
DEFAULT_JUDGE_MAX_TOKENS = 4096
# Cap how much of the last response + recent messages we send to the judge.
_JUDGE_RESPONSE_SNIPPET_CHARS = 4000
# After this many consecutive judge *parse* failures (empty output / non-JSON),
# the loop auto-pauses and points the user at the goal_judge config. API /
# transport errors do NOT count toward this — those are transient. This guards
# against small models (e.g. deepseek-v4-flash) that cannot follow the strict
# JSON reply contract; without it the loop runs until the turn budget is
# exhausted with every reply shaped like `judge returned empty response` or
# `judge reply was not JSON`.
DEFAULT_MAX_CONSECUTIVE_PARSE_FAILURES = 3


CONTINUATION_PROMPT_TEMPLATE = (
    "[Continuing toward your standing goal]\n"
    "Goal: {goal}\n\n"
    "Continue working toward this goal. Take the next concrete step. "
    "If you believe the goal is complete, state so explicitly and stop. "
    "If you are blocked and need input from the user, say so clearly and stop."
)

# Used when the user has added one or more /subgoal criteria. Surfaced
# to the agent verbatim so it sees what to target on the next turn,
# and surfaced to the judge so the verdict considers them too.
CONTINUATION_PROMPT_WITH_SUBGOALS_TEMPLATE = (
    "[Continuing toward your standing goal]\n"
    "Goal: {goal}\n\n"
    "Additional criteria the user added mid-loop:\n"
    "{subgoals_block}\n\n"
    "Continue working toward the goal AND all additional criteria. Take "
    "the next concrete step. If you believe the goal and every "
    "additional criterion are complete, state so explicitly and stop. "
    "If you are blocked and need input from the user, say so clearly "
    "and stop."
)


JUDGE_SYSTEM_PROMPT = (
    "You are a strict judge evaluating whether an autonomous agent has "
    "achieved a user's stated goal. You receive the goal text and the "
    "agent's most recent response. Your only job is to decide whether "
    "the goal is fully satisfied based on that response.\n\n"
    "A goal is DONE only when:\n"
    "- The response explicitly confirms the goal was completed, OR\n"
    "- The response clearly shows the final deliverable was produced, OR\n"
    "- The response explains the goal is unachievable / blocked / needs "
    "user input (treat this as DONE with reason describing the block).\n\n"
    "Otherwise the goal is NOT done — CONTINUE.\n\n"
    "Reply ONLY with a single JSON object on one line:\n"
    '{\"done\": <true|false>, \"reason\": \"<one-sentence rationale>\"}'
)


JUDGE_USER_PROMPT_TEMPLATE = (
    "Goal:\n{goal}\n\n"
    "Agent's most recent response:\n{response}\n\n"
    "Current time: {current_time}\n\n"
    "Is the goal satisfied?"
)

# Used when the user has added /subgoal criteria. The judge must
# evaluate ALL of them being met, not just the original goal.
JUDGE_USER_PROMPT_WITH_SUBGOALS_TEMPLATE = (
    "Goal:\n{goal}\n\n"
    "Additional criteria the user added mid-loop (all must also be "
    "satisfied for the goal to be DONE):\n{subgoals_block}\n\n"
    "Agent's most recent response:\n{response}\n\n"
    "Current time: {current_time}\n\n"
    "Decision: For each numbered criterion above, find concrete "
    "evidence in the agent's response that the criterion is "
    "satisfied. Do not accept generic phrases like 'all requirements "
    "met' or 'implying it was done' — require specific evidence (a "
    "file contents excerpt, an output line, a command result). If "
    "ANY criterion lacks specific evidence in the response, the goal "
    "is NOT done — return CONTINUE.\n\n"
    "Is the goal AND every additional criterion satisfied?"
)


# ──────────────────────────────────────────────────────────────────────
# Dataclass
# ──────────────────────────────────────────────────────────────────────


@dataclass
class GoalState:
    """Serializable goal state stored per session."""

    goal: str
    status: str = "active"          # active | paused | done | cleared
    turns_used: int = 0
    max_turns: int = DEFAULT_MAX_TURNS
    created_at: float = 0.0
    last_turn_at: float = 0.0
    last_verdict: Optional[str] = None        # "done" | "continue" | "skipped"
    last_reason: Optional[str] = None
    paused_reason: Optional[str] = None       # why we auto-paused (budget, etc.)
    consecutive_parse_failures: int = 0       # judge-output parse failures in a row
    # Mads-review gate metadata. V1 is manual: the goal pauses with a
    # self-contained handoff screen; the user decides whether to run review,
    # accept, resume, or clear.
    mads_reviews_used: int = 0
    last_mads_review_turn: int = 0
    last_mads_verdict: Optional[str] = None
    last_mads_reason: Optional[str] = None
    review_recommended_reason: Optional[str] = None
    # User-added criteria appended mid-loop via the /subgoal command.
    # When non-empty the judge prompt and continuation prompt both
    # include them so the agent works toward them and the judge factors
    # them into the verdict. Backwards-compatible: defaults to empty so
    # old state_meta rows load unchanged.
    subgoals: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "GoalState":
        data = json.loads(raw)
        raw_subgoals = data.get("subgoals") or []
        subgoals: List[str] = []
        if isinstance(raw_subgoals, list):
            subgoals = [str(s).strip() for s in raw_subgoals if str(s).strip()]
        return cls(
            goal=data.get("goal", ""),
            status=data.get("status", "active"),
            turns_used=int(data.get("turns_used", 0) or 0),
            max_turns=int(data.get("max_turns", DEFAULT_MAX_TURNS) or DEFAULT_MAX_TURNS),
            created_at=float(data.get("created_at", 0.0) or 0.0),
            last_turn_at=float(data.get("last_turn_at", 0.0) or 0.0),
            last_verdict=data.get("last_verdict"),
            last_reason=data.get("last_reason"),
            paused_reason=data.get("paused_reason"),
            consecutive_parse_failures=int(data.get("consecutive_parse_failures", 0) or 0),
            mads_reviews_used=int(data.get("mads_reviews_used", 0) or 0),
            last_mads_review_turn=int(data.get("last_mads_review_turn", 0) or 0),
            last_mads_verdict=data.get("last_mads_verdict"),
            last_mads_reason=data.get("last_mads_reason"),
            review_recommended_reason=data.get("review_recommended_reason"),
            subgoals=subgoals,
        )

    # --- subgoals helpers -------------------------------------------------

    def render_subgoals_block(self) -> str:
        """Render the subgoals as a numbered ``- N. text`` block. Empty
        when no subgoals exist."""
        if not self.subgoals:
            return ""
        return "\n".join(f"- {i}. {text}" for i, text in enumerate(self.subgoals, start=1))


# ──────────────────────────────────────────────────────────────────────
# Persistence (SessionDB state_meta)
# ──────────────────────────────────────────────────────────────────────


def _meta_key(session_id: str) -> str:
    return f"goal:{session_id}"


_DB_CACHE: Dict[str, Any] = {}


def _get_session_db() -> Optional[Any]:
    """Return a SessionDB instance for the current HERMES_HOME.

    SessionDB has no built-in singleton, but opening a new connection per
    /goal call would thrash the file. We cache one instance per
    ``hermes_home`` path so profile switches still pick up the right DB.
    Defensive against import/instantiation failures so tests and
    non-standard launchers can still use the GoalManager.
    """
    try:
        from hermes_constants import get_hermes_home
        from hermes_state import SessionDB

        home = str(get_hermes_home())
    except Exception as exc:  # pragma: no cover
        logger.debug("GoalManager: SessionDB bootstrap failed (%s)", exc)
        return None

    cached = _DB_CACHE.get(home)
    if cached is not None:
        return cached
    try:
        db = SessionDB()
    except Exception as exc:  # pragma: no cover
        logger.debug("GoalManager: SessionDB() raised (%s)", exc)
        return None
    _DB_CACHE[home] = db
    return db


def load_goal(session_id: str) -> Optional[GoalState]:
    """Load the goal for a session, or None if none exists."""
    if not session_id:
        return None
    db = _get_session_db()
    if db is None:
        return None
    try:
        raw = db.get_meta(_meta_key(session_id))
    except Exception as exc:
        logger.debug("GoalManager: get_meta failed: %s", exc)
        return None
    if not raw:
        return None
    try:
        return GoalState.from_json(raw)
    except Exception as exc:
        logger.warning("GoalManager: could not parse stored goal for %s: %s", session_id, exc)
        return None


def save_goal(session_id: str, state: GoalState) -> None:
    """Persist a goal to SessionDB. No-op if DB unavailable."""
    if not session_id:
        return
    db = _get_session_db()
    if db is None:
        return
    try:
        db.set_meta(_meta_key(session_id), state.to_json())
    except Exception as exc:
        logger.debug("GoalManager: set_meta failed: %s", exc)


def clear_goal(session_id: str) -> None:
    """Mark a goal cleared in the DB (preserved for audit, status=cleared)."""
    state = load_goal(session_id)
    if state is None:
        return
    state.status = "cleared"
    save_goal(session_id, state)


# ──────────────────────────────────────────────────────────────────────
# Judge
# ──────────────────────────────────────────────────────────────────────


def _truncate(text: str, limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "… [truncated]"


_JSON_OBJECT_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _goal_judge_max_tokens() -> int:
    """Resolve auxiliary.goal_judge.max_tokens, falling back to the default.

    ``load_config()`` is cached on the config file's (mtime, size), so calling
    this once per judge turn is cheap. A non-positive or non-int value falls
    back to the default rather than crashing the goal loop.
    """
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        value = (
            (cfg.get("auxiliary") or {})
            .get("goal_judge", {})
            .get("max_tokens", DEFAULT_JUDGE_MAX_TOKENS)
        )
        value = int(value)
        if value > 0:
            return value
    except Exception:
        pass
    return DEFAULT_JUDGE_MAX_TOKENS


def _parse_judge_response(raw: str) -> Tuple[bool, str, bool]:
    """Parse the judge's reply. Fail-open to ``(False, "<reason>", parse_failed)``.

    Returns ``(done, reason, parse_failed)``. ``parse_failed`` is True when the
    judge returned output that couldn't be interpreted as the expected JSON
    verdict (empty body, prose, malformed JSON). Callers use that flag to
    auto-pause after N consecutive parse failures so a weak judge model
    doesn't silently burn the turn budget.
    """
    if not raw:
        return False, "judge returned empty response", True

    text = raw.strip()

    # Strip markdown code fences the model may wrap JSON in.
    if text.startswith("```"):
        text = text.strip("`")
        # Peel off leading json/JSON/etc tag
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1:]

    # First try: parse the whole blob.
    data: Optional[Dict[str, Any]] = None
    try:
        data = json.loads(text)
    except Exception:
        # Second try: pull the first JSON object out.
        match = _JSON_OBJECT_RE.search(text)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                data = None

    if not isinstance(data, dict):
        return False, f"judge reply was not JSON: {_truncate(raw, 200)!r}", True

    done_val = data.get("done")
    if isinstance(done_val, str):
        done = done_val.strip().lower() in {"true", "yes", "1", "done"}
    else:
        done = bool(done_val)
    reason = str(data.get("reason") or "").strip()
    if not reason:
        reason = "no reason provided"
    return done, reason, False


_IMPORTANT_GOAL_KEYWORDS = {
    "architecture", "autonomy", "autonomous", "background", "cron",
    "deploy", "eval", "evaluation", "gateway", "implement", "improve",
    "mads", "memory", "patch", "publish", "release", "restart",
    "service", "skill", "test",
}


def classify_goal_topic(goal: str, subgoals: Optional[List[str]] = None) -> str:
    """Return a deterministic topic bucket for Mads-review prompt examples."""
    text = " ".join([goal or "", *((subgoals or []))]).lower()
    if any(k in text for k in ["deploy", "restart", "service", "production", "rollback", "credential"]):
        return "ops"
    if any(k in text for k in ["test", "eval", "evaluation", "reliability", "regression"]):
        return "evals"
    if any(k in text for k in ["hermes", "goal", "agent", "mads", "autonomy", "autonomous", "architecture"]):
        return "agent_architecture"
    if any(k in text for k in ["website", "content", "seo", "copy", "homepage", "public", "identity"]):
        return "public_content"
    if any(k in text for k in ["research", "tool", "library", "compare", "alternative", "adoption"]):
        return "research"
    if any(k in text for k in ["cron", "automation", "background", "scheduler", "job"]):
        return "automation"
    if any(k in text for k in ["memory", "skill", "self-improvement", "improvement", "provenance"]):
        return "memory_skills"
    if any(k in text for k in ["patch", "code", "repo", "implementation", "bug", "fix"]):
        return "code_patch"
    return "general"


def suggested_mads_review_prompts(topic: str) -> List[str]:
    examples = {
        "agent_architecture": [
            "Focus on hidden autonomy risks, queued continuation bugs, state-machine simplicity, and missing tests.",
            "Challenge whether this keeps Hermes as the control plane and Mads as reviewer only.",
            "Look for any path where the goal could continue without explicit approval.",
        ],
        "code_patch": [
            "Review the patch for correctness, regressions, backwards compatibility, and missing tests.",
            "Focus on edge cases, failure modes, and whether the smallest safe change was made.",
            "Check whether unrelated refactor or scope creep slipped in.",
        ],
        "evals": [
            "Check whether the tests actually prove the behavior or only test implementation details.",
            "Look for missing negative cases, stale-loop cases, and false-pass risks.",
            "Challenge the eval design: what would make this look improved while still being unsafe?",
        ],
        "ops": [
            "Review rollout risk, rollback path, verification commands, and what should block deployment.",
            "Look for hidden production side effects, credential risks, and service-restart hazards.",
            "Check whether this can be verified read-only before any live action.",
        ],
        "public_content": [
            "Review for factual accuracy, public trust risks, broken links, and AI-slop language.",
            "Check whether claims are evidence-backed and identity/social links are verified.",
            "Focus on user perception, clarity, and anything that could damage credibility.",
        ],
        "research": [
            "Challenge the recommendation. Look for better alternatives, weak evidence, and maintenance risks.",
            "Focus on whether the sources justify the conclusion and what is still uncertain.",
            "Compare practical adoption cost versus claimed benefit.",
        ],
        "automation": [
            "Check for runaway automation, duplicate execution, noisy alerts, and missing failure handling.",
            "Focus on idempotency, logging, retry behavior, and safe defaults.",
            "Look for cases where the job silently fails or keeps acting after it should stop.",
        ],
        "memory_skills": [
            "Check whether this creates durable improvement or just more accumulated state.",
            "Focus on provenance, eval gates, stale memory risk, and rollback.",
            "Challenge whether this belongs in memory, a skill, docs, config, or evals.",
        ],
        "general": [
            "Challenge the result. Look for weak evidence, missing verification, and hidden assumptions.",
            "Focus on whether Hermes is falsely declaring completion or skipping an important check.",
            "Identify the smallest concrete next action if this should be revised.",
        ],
    }
    return examples.get(topic, examples["general"])


def is_mads_review_worthy_goal(goal: str, subgoals: Optional[List[str]] = None) -> bool:
    text = " ".join([goal or "", *((subgoals or []))]).lower()
    # Keep this conservative: v1 should pause at important work stages, not
    # every explanatory goal that happens to mention Hermes or /goal.
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in _IMPORTANT_GOAL_KEYWORDS)


def render_mads_review_pause_message(state: GoalState, trigger: str, reason: str) -> str:
    topic = classify_goal_topic(state.goal, state.subgoals)
    examples = suggested_mads_review_prompts(topic)
    suggested = examples[0]
    lines = [
        "⏸️ Goal paused — Mads review recommended",
        "",
        "🔎 Why this paused",
        reason,
        "",
        "📍 Current state",
        f"- 🎯 Goal: {state.goal}",
        f"- 🔢 Turns: {state.turns_used}/{state.max_turns}",
        f"- 🚦 Trigger: {trigger}",
        "- 💤 Standby: yes — this goal will not continue on its own.",
        "",
        "✅ Recommended next step",
        f"  /goal review mads {suggested}",
        "",
        "🧭 Other options",
        "- 👀 /goal review",
        "  Preview the review packet without sending.",
        "- 🧠 /goal review mads",
        "  Use the default Mads review packet.",
        "- ✍️ /goal review mads <requirements>",
        "  Add your own focus areas before review.",
        "- ✅ /goal accept",
        "  Mark done without Mads.",
        "- ▶️ /goal resume",
        "  Continue Hermes-only.",
        "- 🛑 /goal clear",
        "  Stop this goal.",
        "",
        "💡 Suggested Mads prompts for this topic",
    ]
    lines.extend(f"{i}. /goal review mads {text}" for i, text in enumerate(examples, start=1))
    return "\n".join(lines)


def render_mads_review_packet(state: GoalState, extra_requirements: str = "") -> str:
    topic = classify_goal_topic(state.goal, state.subgoals)
    examples = suggested_mads_review_prompts(topic)
    subgoals_block = state.render_subgoals_block() if state.subgoals else "(none)"
    req = (extra_requirements or "").strip() or examples[0]
    return "\n".join([
        "🧠 Mads review packet",
        "",
        "🎯 Goal",
        state.goal,
        "",
        "📌 Subgoals",
        subgoals_block,
        "",
        "📍 Current state",
        f"- 🔢 turns used: {state.turns_used}/{state.max_turns}",
        f"- ⚖️ last judge verdict: {state.last_verdict or 'unknown'}",
        f"- 💬 last judge reason: {state.last_reason or 'unknown'}",
        f"- 🚦 review trigger: {state.review_recommended_reason or 'manual'}",
        "- 🧍 review mode: pause_for_review",
        "- 💤 standby: the goal will not continue on its own while paused",
        "",
        "✍️ User-added review requirements",
        req,
        "",
        "🚧 Rules",
        "- 👀 Read-only review.",
        "- 🚫 Do not edit files.",
        "- 🚫 Do not deploy, publish, restart services, change credentials, or perform destructive actions.",
        "- 🔎 Focus on concrete risks, missing verification, and whether Hermes is falsely declaring completion.",
        "",
        "📤 Return",
        "1. ✅ Verdict: accept | revise | blocked | needs Henry decision",
        "2. ⚠️ Highest-risk missed issue",
        "3. ➡️ Concrete next action for Hermes",
        "4. 🧪 Evidence required for completion",
        "5. 📊 Confidence: low | medium | high",
    ])


def should_recommend_mads_review(state: GoalState, verdict: str) -> Tuple[bool, str, str]:
    if state.mads_reviews_used > 0 or state.review_recommended_reason:
        return False, "", ""
    if verdict == "done" and is_mads_review_worthy_goal(state.goal, state.subgoals):
        return True, "before_done", (
            "This goal appears complete, but it touches an important area where "
            "a second-model review is useful before accepting completion."
        )
    return False, "", ""


def judge_goal(
    goal: str,
    last_response: str,
    *,
    timeout: float = DEFAULT_JUDGE_TIMEOUT,
    subgoals: Optional[List[str]] = None,
) -> Tuple[str, str, bool]:
    """Ask the auxiliary model whether the goal is satisfied.

    Returns ``(verdict, reason, parse_failed)`` where verdict is ``"done"``,
    ``"continue"``, or ``"skipped"`` (when the judge couldn't be reached).

    ``parse_failed`` is True only when the judge call succeeded but its output
    was unusable (empty or non-JSON). API/transport errors return False — they
    are transient and should fail-open silently. Callers use this flag to
    auto-pause after N consecutive parse failures (see
    ``DEFAULT_MAX_CONSECUTIVE_PARSE_FAILURES``).

    ``subgoals`` is an optional list of user-added criteria (from
    ``/subgoal``) that the judge must also factor into its DONE/CONTINUE
    decision. When non-empty the prompt switches to the with-subgoals
    template; otherwise behavior is identical to the original judge.

    This is deliberately fail-open: any error returns ``("continue", "...", False)``
    so a broken judge doesn't wedge progress — the turn budget and the
    consecutive-parse-failures auto-pause are the backstops.
    """
    if not goal.strip():
        return "skipped", "empty goal", False
    if not last_response.strip():
        # No substantive reply this turn — almost certainly not done yet.
        return "continue", "empty response (nothing to evaluate)", False

    try:
        from agent.auxiliary_client import get_auxiliary_extra_body, get_text_auxiliary_client
    except Exception as exc:
        logger.debug("goal judge: auxiliary client import failed: %s", exc)
        return "continue", "auxiliary client unavailable", False

    try:
        client, model = get_text_auxiliary_client("goal_judge")
    except Exception as exc:
        logger.debug("goal judge: get_text_auxiliary_client failed: %s", exc)
        return "continue", "auxiliary client unavailable", False

    if client is None or not model:
        return "continue", "no auxiliary client configured", False

    # Build the prompt — pick the with-subgoals variant when applicable.
    clean_subgoals = [s.strip() for s in (subgoals or []) if s and s.strip()]
    current_time = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    if clean_subgoals:
        subgoals_block = "\n".join(
            f"- {i}. {text}" for i, text in enumerate(clean_subgoals, start=1)
        )
        prompt = JUDGE_USER_PROMPT_WITH_SUBGOALS_TEMPLATE.format(
            goal=_truncate(goal, 2000),
            subgoals_block=_truncate(subgoals_block, 2000),
            response=_truncate(last_response, _JUDGE_RESPONSE_SNIPPET_CHARS),
            current_time=current_time,
        )
    else:
        prompt = JUDGE_USER_PROMPT_TEMPLATE.format(
            goal=_truncate(goal, 2000),
            response=_truncate(last_response, _JUDGE_RESPONSE_SNIPPET_CHARS),
            current_time=current_time,
        )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=_goal_judge_max_tokens(),
            timeout=timeout,
            extra_body=get_auxiliary_extra_body() or None,
        )
    except Exception as exc:
        logger.info("goal judge: API call failed (%s) — falling through to continue", exc)
        return "continue", f"judge error: {type(exc).__name__}", False

    try:
        raw = resp.choices[0].message.content or ""
    except Exception:
        raw = ""

    done, reason, parse_failed = _parse_judge_response(raw)
    verdict = "done" if done else "continue"
    logger.info("goal judge: verdict=%s reason=%s", verdict, _truncate(reason, 120))
    return verdict, reason, parse_failed


# ──────────────────────────────────────────────────────────────────────
# GoalManager — the orchestration surface CLI + gateway talk to
# ──────────────────────────────────────────────────────────────────────


class GoalManager:
    """Per-session goal state + continuation decisions.

    The CLI and gateway each hold one ``GoalManager`` per live session.

    Methods:

    - ``set(goal)`` — start a new standing goal.
    - ``clear()`` — remove the active goal.
    - ``pause()`` / ``resume()`` — explicit user controls.
    - ``status()`` — printable one-liner.
    - ``evaluate_after_turn(last_response)`` — call the judge, update state,
      and return a decision dict the caller uses to drive the next turn.
    - ``next_continuation_prompt()`` — the canonical user-role message to
      feed back into ``run_conversation``.
    """

    def __init__(self, session_id: str, *, default_max_turns: int = DEFAULT_MAX_TURNS):
        self.session_id = session_id
        self.default_max_turns = int(default_max_turns or DEFAULT_MAX_TURNS)
        self._state: Optional[GoalState] = load_goal(session_id)

    # --- introspection ------------------------------------------------

    @property
    def state(self) -> Optional[GoalState]:
        return self._state

    def is_active(self) -> bool:
        return self._state is not None and self._state.status == "active"

    def has_goal(self) -> bool:
        return self._state is not None and self._state.status in {"active", "paused"}

    def status_line(self) -> str:
        s = self._state
        if s is None or s.status in {"cleared",}:
            return "No active goal. Set one with /goal <text>."
        turns = f"{s.turns_used}/{s.max_turns} turns"
        sub = f", {len(s.subgoals)} subgoal{'s' if len(s.subgoals) != 1 else ''}" if s.subgoals else ""
        if s.status == "active":
            return f"⊙ Goal (active, {turns}{sub}): {s.goal}"
        if s.status == "paused":
            extra = f" — {s.paused_reason}" if s.paused_reason else ""
            return f"⏸ Goal (paused, {turns}{sub}{extra}): {s.goal}"
        if s.status == "done":
            return f"✓ Goal done ({turns}{sub}): {s.goal}"
        return f"Goal ({s.status}, {turns}{sub}): {s.goal}"

    # --- mutation -----------------------------------------------------

    def set(self, goal: str, *, max_turns: Optional[int] = None) -> GoalState:
        goal = (goal or "").strip()
        if not goal:
            raise ValueError("goal text is empty")
        state = GoalState(
            goal=goal,
            status="active",
            turns_used=0,
            max_turns=int(max_turns) if max_turns else self.default_max_turns,
            created_at=time.time(),
            last_turn_at=0.0,
        )
        self._state = state
        save_goal(self.session_id, state)
        return state

    def pause(self, reason: str = "user-paused") -> Optional[GoalState]:
        if not self._state:
            return None
        self._state.status = "paused"
        self._state.paused_reason = reason
        save_goal(self.session_id, self._state)
        return self._state

    def resume(self, *, reset_budget: bool = True) -> Optional[GoalState]:
        if not self._state:
            return None
        self._state.status = "active"
        self._state.paused_reason = None
        if reset_budget:
            self._state.turns_used = 0
        save_goal(self.session_id, self._state)
        return self._state

    def clear(self) -> None:
        if self._state is None:
            return
        self._state.status = "cleared"
        save_goal(self.session_id, self._state)
        self._state = None

    def mark_done(self, reason: str) -> None:
        if not self._state:
            return
        self._state.status = "done"
        self._state.last_verdict = "done"
        self._state.last_reason = reason
        save_goal(self.session_id, self._state)

    def accept(self, reason: str = "accepted without Mads review") -> Optional[GoalState]:
        """Mark a paused/review-recommended goal done by explicit user choice."""
        if not self._state:
            return None
        self._state.status = "done"
        self._state.last_verdict = "done"
        self._state.last_reason = reason
        self._state.paused_reason = None
        save_goal(self.session_id, self._state)
        return self._state

    def render_mads_review(self, extra_requirements: str = "", *, mark_sent: bool = False) -> Optional[str]:
        """Render the bounded Mads review packet for the active/paused goal.

        V1 does not silently dispatch Mads; callers can show this packet or
        hand it to a separate Mads/OpenClaw lane. ``mark_sent`` records that
        the user explicitly requested the Mads packet.
        """
        if not self._state or not self.has_goal():
            return None
        if mark_sent:
            self._state.mads_reviews_used += 1
            self._state.last_mads_review_turn = self._state.turns_used
            self._state.last_mads_verdict = "packet-prepared"
            self._state.last_mads_reason = (extra_requirements or "default review packet").strip()
            save_goal(self.session_id, self._state)
        return render_mads_review_packet(self._state, extra_requirements)

    # --- /subgoal user controls ---------------------------------------

    def add_subgoal(self, text: str) -> str:
        """Append a user-added criterion to the active goal. Requires
        ``has_goal()``; raises ``RuntimeError`` otherwise.

        Returns the cleaned text so the caller can show it back to the user.
        """
        if self._state is None or not self.has_goal():
            raise RuntimeError("no active goal")
        text = (text or "").strip()
        if not text:
            raise ValueError("subgoal text is empty")
        self._state.subgoals.append(text)
        save_goal(self.session_id, self._state)
        return text

    def remove_subgoal(self, index_1based: int) -> str:
        """Remove a subgoal by 1-based index. Returns the removed text."""
        if self._state is None or not self.has_goal():
            raise RuntimeError("no active goal")
        idx = int(index_1based) - 1
        if idx < 0 or idx >= len(self._state.subgoals):
            raise IndexError(
                f"index out of range (1..{len(self._state.subgoals)})"
            )
        removed = self._state.subgoals.pop(idx)
        save_goal(self.session_id, self._state)
        return removed

    def clear_subgoals(self) -> int:
        """Wipe all subgoals. Returns the previous count."""
        if self._state is None or not self.has_goal():
            raise RuntimeError("no active goal")
        prev = len(self._state.subgoals)
        self._state.subgoals = []
        save_goal(self.session_id, self._state)
        return prev

    def render_subgoals(self) -> str:
        """Public helper for the /subgoal slash command."""
        if self._state is None:
            return "(no active goal)"
        if not self._state.subgoals:
            return "(no subgoals — use /subgoal <text> to add criteria)"
        return self._state.render_subgoals_block()

    # --- the main entry point called after every turn -----------------

    def evaluate_after_turn(
        self,
        last_response: str,
        *,
        user_initiated: bool = True,
    ) -> Dict[str, Any]:
        """Run the judge and update state. Return a decision dict.

        ``user_initiated`` distinguishes a real user prompt (True) from a
        continuation prompt we fed ourselves (False). Both increment
        ``turns_used`` because both consume model budget.

        Decision keys:
          - ``status``: current goal status after update
          - ``should_continue``: bool — caller should fire another turn
          - ``continuation_prompt``: str or None
          - ``verdict``: "done" | "continue" | "skipped" | "inactive"
          - ``reason``: str
          - ``message``: user-visible one-liner to print/send
        """
        state = self._state
        if state is None or state.status != "active":
            return {
                "status": state.status if state else None,
                "should_continue": False,
                "continuation_prompt": None,
                "verdict": "inactive",
                "reason": "no active goal",
                "message": "",
            }

        # Count the turn that just finished.
        state.turns_used += 1
        state.last_turn_at = time.time()

        verdict, reason, parse_failed = judge_goal(
            state.goal, last_response, subgoals=state.subgoals or None
        )
        state.last_verdict = verdict
        state.last_reason = reason

        # Track consecutive judge parse failures. Reset on any usable reply,
        # including API / transport errors (parse_failed=False) so a flaky
        # network doesn't trip the auto-pause meant for bad judge models.
        if parse_failed:
            state.consecutive_parse_failures += 1
        else:
            state.consecutive_parse_failures = 0

        if verdict == "done":
            should_review, trigger, review_reason = should_recommend_mads_review(state, verdict)
            if should_review:
                state.status = "paused"
                state.paused_reason = f"mads-review-recommended:{trigger}"
                state.review_recommended_reason = trigger
                save_goal(self.session_id, state)
                return {
                    "status": "paused",
                    "should_continue": False,
                    "continuation_prompt": None,
                    "verdict": "review_recommended",
                    "reason": review_reason,
                    "message": render_mads_review_pause_message(state, trigger, review_reason),
                }

            state.status = "done"
            save_goal(self.session_id, state)
            return {
                "status": "done",
                "should_continue": False,
                "continuation_prompt": None,
                "verdict": "done",
                "reason": reason,
                "message": f"✓ Goal achieved: {reason}",
            }

        # Auto-pause when the judge model can't produce the expected JSON
        # verdict N turns in a row. Points the user at the goal_judge config
        # so they can route this side task to a model that follows the
        # contract (e.g. google/gemini-3-flash-preview). Without this guard,
        # weak judge models burn the entire turn budget returning prose or
        # empty strings.
        if state.consecutive_parse_failures >= DEFAULT_MAX_CONSECUTIVE_PARSE_FAILURES:
            state.status = "paused"
            state.paused_reason = (
                f"judge model returned unparseable output {state.consecutive_parse_failures} turns in a row"
            )
            save_goal(self.session_id, state)
            return {
                "status": "paused",
                "should_continue": False,
                "continuation_prompt": None,
                "verdict": "continue",
                "reason": reason,
                "message": (
                    f"⏸ Goal paused — the judge model ({state.consecutive_parse_failures} turns) "
                    "isn't returning the required JSON verdict. Route the judge to a stricter "
                    "model in ~/.hermes/config.yaml:\n"
                    "  auxiliary:\n"
                    "    goal_judge:\n"
                    "      provider: openrouter\n"
                    "      model: google/gemini-3-flash-preview\n"
                    "Then /goal resume to continue."
                ),
            }

        if state.turns_used >= state.max_turns:
            state.status = "paused"
            state.paused_reason = f"turn budget exhausted ({state.turns_used}/{state.max_turns})"
            save_goal(self.session_id, state)
            return {
                "status": "paused",
                "should_continue": False,
                "continuation_prompt": None,
                "verdict": "continue",
                "reason": reason,
                "message": (
                    f"⏸ Goal paused — {state.turns_used}/{state.max_turns} turns used. "
                    "Use /goal resume to keep going, or /goal clear to stop."
                ),
            }

        save_goal(self.session_id, state)
        return {
            "status": "active",
            "should_continue": True,
            "continuation_prompt": self.next_continuation_prompt(),
            "verdict": "continue",
            "reason": reason,
            "message": (
                f"↻ Continuing toward goal ({state.turns_used}/{state.max_turns}): {reason}"
            ),
        }

    def next_continuation_prompt(self) -> Optional[str]:
        if not self._state or self._state.status != "active":
            return None
        if self._state.subgoals:
            return CONTINUATION_PROMPT_WITH_SUBGOALS_TEMPLATE.format(
                goal=self._state.goal,
                subgoals_block=self._state.render_subgoals_block(),
            )
        return CONTINUATION_PROMPT_TEMPLATE.format(goal=self._state.goal)


__all__ = [
    "GoalState",
    "GoalManager",
    "CONTINUATION_PROMPT_TEMPLATE",
    "CONTINUATION_PROMPT_WITH_SUBGOALS_TEMPLATE",
    "JUDGE_USER_PROMPT_TEMPLATE",
    "JUDGE_USER_PROMPT_WITH_SUBGOALS_TEMPLATE",
    "DEFAULT_MAX_TURNS",
    "load_goal",
    "save_goal",
    "clear_goal",
    "judge_goal",
]
