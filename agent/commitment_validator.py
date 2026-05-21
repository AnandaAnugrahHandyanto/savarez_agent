"""Reply-side commitment validator (S-0518-01 Type E observability).

Detects when Coach's outgoing reply text contains a *future-tense sub-agent
commitment* (e.g. "I'll have Analyst put a cheat sheet together",
"Publicist will draft the cover letter by morning") but no
`enqueue_action` tool call was made this turn — i.e. an *empty promise*
where the user sees a sub-agent action being announced but no backend
action_queue entry was created to back it up.

**This module currently OBSERVES ONLY** — it logs detection results to
`agent.log`, does not mutate the reply or backend state. Once accuracy is
verified across a real traffic sample, the same hook point can be extended
to auto-emit an `enqueue_action` call (or block the reply for retry).

Called from `gateway/run.py` after `response ready` log, before
`_send_with_retry`. Failures are silent — this is a soft observability
layer, not a hard gate.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


_ENQUEUE_TOOL_NAMES = {
    "enqueue_action",
    "mcp_artemis_tools_enqueue_action",
}

# Below this reply length, skip the auxiliary call entirely — short replies
# ("Makes sense.", "👍", "OK on it.") can't contain a real future-tense
# sub-agent commitment.
_MIN_REPLY_LEN_FOR_CHECK = 80


_VALIDATOR_PROMPT = """\
You are a structural validator for a coaching agent's reply. The agent
("Coach") has a backend team of sub-agents — Scout (job-market scanning),
Analyst (data analysis), Publicist (writing materials). When Coach commits a
future sub-agent action in its reply ("Analyst will put a cheat sheet
together", "Publicist will draft the cover letter by morning", "I'll have
Scout widen the scan"), the commitment MUST be backed by an `enqueue_action`
tool call so the backend has a queue entry. If Coach makes such a commitment
in prose but does NOT call `enqueue_action`, that's an "empty promise" —
user sees the announcement, backend has no record.

Your job: given Coach's reply text below, decide whether it contains a
future-tense sub-agent commitment that would require an `enqueue_action`
call to be valid.

Rules:
- ONLY flag *future-tense* or *modal* commitments where a sub-agent (or
  "the team") is the agent of a future action: "X will Y", "X is going to
  Y", "I'll have X do Y", "let me get X to Y", "X can have it ready by Y".
- Past or in-flight references DO NOT count: "Analyst already flagged...",
  "Scout's recalibrating" (in-flight), "Publicist drafted..." (past).
- "Coach is going to do X" with no sub-agent involved → does NOT count.
- Vague mentions ("your team is here for you") with no specific work
  commitment → does NOT count.
- Modal capability framing ("Publicist can sharpen your materials if you'd
  like") without commitment → flag with confidence "low" only.

Return STRICT JSON, no prose, no markdown fence:

{
  "has_unmet_commitment": <true|false>,
  "sub_agent": "<scout|analyst|publicist|team|null>",
  "future_tense_phrase": "<verbatim phrase from the reply that triggered the flag, or null>",
  "confidence": "<high|medium|low>",
  "reasoning": "<one short sentence>"
}

Coach's reply:
\"\"\"
{reply_text}
\"\"\"
"""


def _was_enqueue_called(agent_messages: list[dict] | None) -> bool:
    """True if any message in this turn's agent_messages contains a
    tool_call to enqueue_action."""
    if not agent_messages:
        return False
    for msg in agent_messages:
        if not isinstance(msg, dict):
            continue
        tcs = msg.get("tool_calls") or []
        for tc in tcs:
            if not isinstance(tc, dict):
                continue
            fn = (tc.get("function") or {}).get("name", "")
            if fn in _ENQUEUE_TOOL_NAMES:
                return True
    return False


def _parse_validator_response(raw: str) -> dict[str, Any] | None:
    """Tolerant JSON parse. Returns None on any failure."""
    if not raw:
        return None
    s = raw.strip()
    # Strip markdown fence if present.
    if s.startswith("```"):
        lines = s.splitlines()
        s = "\n".join(lines[1:-1]) if len(lines) >= 2 else s
        if s.startswith("json\n"):
            s = s[5:]
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def check_unmet_commitment(
    reply_text: str,
    agent_messages: list[dict] | None,
    *,
    chat_id: str = "",
) -> dict[str, Any]:
    """Inspect Coach's outgoing reply for an unmet sub-agent commitment.

    Returns a dict describing the check outcome. Logs a structured line to
    `agent.log` so accuracy can be evaluated across runs.

    Schema (all keys always present so log parsing is uniform):
      {
        "checked": bool,             # auxiliary LLM was called
        "skipped": str|None,         # reason for skip if not checked
        "has_unmet_commitment": bool,
        "sub_agent": str|None,
        "future_tense_phrase": str|None,
        "confidence": str|None,      # high|medium|low
        "reasoning": str|None,
      }
    """
    out: dict[str, Any] = {
        "checked": False,
        "skipped": None,
        "has_unmet_commitment": False,
        "sub_agent": None,
        "future_tense_phrase": None,
        "confidence": None,
        "reasoning": None,
    }

    if not reply_text or len(reply_text) < _MIN_REPLY_LEN_FOR_CHECK:
        out["skipped"] = "reply_too_short"
        _log_result(chat_id, out)
        return out

    if _was_enqueue_called(agent_messages):
        out["skipped"] = "enqueue_called"
        _log_result(chat_id, out)
        return out

    # Auxiliary LLM call. Lazy-import so module load doesn't pull in the
    # client at import time (helps with test isolation).
    try:
        from agent.auxiliary_client import call_llm  # noqa: WPS433
    except Exception as e:
        out["skipped"] = f"client_import_failed:{type(e).__name__}"
        _log_result(chat_id, out)
        return out

    prompt = _VALIDATOR_PROMPT.replace("{reply_text}", reply_text)
    try:
        response = call_llm(
            task="compression",  # reuse cheap-and-fast aux model slot
            messages=[
                {"role": "system", "content": "You return only strict JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.0,
            timeout=10.0,
        )
        raw = (response.choices[0].message.content or "").strip()
    except Exception as e:
        out["skipped"] = f"aux_call_failed:{type(e).__name__}"
        _log_result(chat_id, out)
        return out

    parsed = _parse_validator_response(raw)
    if parsed is None:
        out["skipped"] = "aux_parse_failed"
        out["reasoning"] = f"raw={raw[:200]!r}"
        _log_result(chat_id, out)
        return out

    out["checked"] = True
    out["has_unmet_commitment"] = bool(parsed.get("has_unmet_commitment"))
    out["sub_agent"] = parsed.get("sub_agent") or None
    out["future_tense_phrase"] = parsed.get("future_tense_phrase") or None
    out["confidence"] = parsed.get("confidence") or None
    out["reasoning"] = parsed.get("reasoning") or None
    _log_result(chat_id, out)
    return out


def _log_result(chat_id: str, out: dict[str, Any]) -> None:
    """Emit a single structured line to agent.log for offline accuracy
    review. Single line so `grep commitment-check:` lifts a clean stream."""
    fields = (
        f"chat={chat_id or 'unknown'}",
        f"checked={out['checked']}",
        f"skipped={out['skipped']}",
        f"mismatch={out['has_unmet_commitment']}",
        f"sub_agent={out['sub_agent']}",
        f"confidence={out['confidence']}",
        f"phrase={out['future_tense_phrase']!r}",
        f"reasoning={out['reasoning']!r}",
    )
    logger.info("commitment-check: %s", " ".join(fields))
