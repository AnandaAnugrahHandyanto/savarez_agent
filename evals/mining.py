from __future__ import annotations

import csv
import io
import json
import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass, field, fields, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml

from .schemas import EvalSchemaError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

MiningSource = Literal["state-db", "trajectories", "cron-outputs"]


@dataclass
class MinedCandidate:
    """A single session or trace that is a candidate for promotion to an eval case."""

    candidate_id: str
    source: MiningSource
    session_id: str
    prompt: str
    final_response: str
    tool_names: list[str]
    tool_call_count: int
    failed: bool
    mined_at: str
    model: str | None = None
    provider: str | None = None
    title: str | None = None
    context: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    elapsed_ms: int | None = None
    reason: str | None = None
    tags: list[str] = field(default_factory=lambda: ["mined", "needs-review"])

    @classmethod
    def from_session_row(
        cls,
        session: dict[str, Any],
        first_user_msg: str,
        last_assistant_msg: str,
        tool_names: list[str],
        *,
        reason: str | None = None,
    ) -> "MinedCandidate":
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        short_id = session.get("id", "unknown")[:12]
        fields_ = {
            "candidate_id": f"mined.state.{short_id}",
            "source": "state-db",
            "session_id": session.get("id", ""),
            "model": session.get("model"),
            "provider": session.get("billing_provider"),
            "title": session.get("title"),
            "prompt": first_user_msg,
            "context": session.get("system_prompt"),
            "final_response": last_assistant_msg,
            "tool_names": tool_names,
            "tool_call_count": session.get("tool_call_count", 0),
            "input_tokens": session.get("input_tokens"),
            "output_tokens": session.get("output_tokens"),
            "estimated_cost_usd": session.get("estimated_cost_usd"),
            "elapsed_ms": _compute_elapsed_ms(session),
            "failed": session.get("end_reason") in ("error", "interrupted") or not last_assistant_msg,
            "reason": reason,
            "tags": ["mined", "state-db", "needs-review"],
            "mined_at": now_iso,
        }
        return cls(**fields_)  # type: ignore[arg-type]

    @classmethod
    def from_trajectory_entry(
        cls,
        entry: dict[str, Any],
        *,
        reason: str | None = None,
    ) -> "MinedCandidate":
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conversations = entry.get("conversations", [])
        first_user = _first_user_message(conversations)
        last_assistant = _last_assistant_message(conversations)
        tool_names = _unique_tool_names_from_conversations(conversations)
        tool_call_count = len(
            [m for m in conversations if m.get("role") == "assistant" and m.get("tool_calls")]
        )
        session_id = entry.get("session_id", entry.get("timestamp", "unknown"))
        short_id = session_id[:12]

        return cls(
            candidate_id=f"mined.traj.{short_id}",
            source="trajectories",
            session_id=str(session_id),
            model=entry.get("model"),
            provider=None,
            title=None,
            prompt=first_user,
            context=None,
            final_response=last_assistant,
            tool_names=tool_names,
            tool_call_count=tool_call_count,
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=None,
            failed=not entry.get("completed", True),
            reason=reason,
            tags=["mined", "trajectory", "needs-review"],
            mined_at=now_iso,
        )


@dataclass
class MiningResult:
    """Summary of a single mining run over one source."""

    source_name: MiningSource
    candidates: list[MinedCandidate]
    total_sessions_scanned: int
    total_candidates: int


# ---------------------------------------------------------------------------
# Session DB mining
# ---------------------------------------------------------------------------

def mine_from_session_db(
    db_path: str | Path,
    *,
    source: str | None = None,
    model: str | None = None,
    failed_only: bool = False,
    min_tool_calls: int = 0,
    min_tokens: int = 0,
    days_back: int | None = None,
    limit: int = 50,
    cursor_factory: Any = None,
) -> MiningResult:
    """Mine candidate eval cases from a Hermes SessionDB (state.db).

    Parameters
    ----------
    db_path :
        Path to the SQLite database.
    source :
        Optional session source filter (e.g. ``\"cli\"``, ``\"telegram\"``).
    model :
        Optional model name filter (LIKE match).
    failed_only :
        Only include sessions with ``end_reason`` in (error, interrupted).
    min_tool_calls :
        Minimum ``tool_call_count`` (helps keep low-noise sessions out).
    min_tokens :
        Minimum total tokens across input + output.
    days_back :
        Only sessions started within this many days.
    limit :
        Maximum candidates to return.
    cursor_factory :
        For testing — pass a pre-opened sqlite3 Cursor to avoid opening
        a real file.  The cursor's ``connection`` is used as-is.
    """
    candidates: list[MinedCandidate] = []

    if cursor_factory is not None:
        conn = cursor_factory.connection
    else:
        db_path = Path(db_path)
        if not db_path.exists():
            logger.warning("Session DB not found at %s", db_path)
            return MiningResult(
                source_name="state-db",
                candidates=[],
                total_sessions_scanned=0,
                total_candidates=0,
            )
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

    try:
        where_clauses: list[str] = []
        params: list[Any] = []

        if source:
            where_clauses.append("s.source = ?")
            params.append(source)
        if model:
            where_clauses.append("s.model LIKE ?")
            params.append(f"%{model}%")
        if failed_only:
            where_clauses.append("s.end_reason IN ('error', 'interrupted')")
        if min_tool_calls > 0:
            where_clauses.append("s.tool_call_count >= ?")
            params.append(min_tool_calls)
        if days_back is not None and days_back > 0:
            cutoff = datetime.now(timezone.utc).timestamp() - (days_back * 86400)
            where_clauses.append("s.started_at >= ?")
            params.append(cutoff)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Fetch sessions ordered by recency
        rows = conn.execute(
            f"SELECT s.* FROM sessions s WHERE {where_sql} ORDER BY s.started_at DESC LIMIT ?",
            [*params, limit],
        ).fetchall()

        total = len(rows)

        for row in rows:
            session = dict(row)
            sid = session.get("id", "")
            if not sid:
                continue

            # Fetch messages for this session
            msgs = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id",
                (sid,),
            ).fetchall()
            msg_dicts = [dict(m) for m in msgs]

            first_user = _first_user_message(msg_dicts)
            last_assistant = _last_assistant_message(msg_dicts)

            # Bail if there's no real user input to build a prompt from
            if not first_user and not last_assistant:
                continue

            tool_names = _unique_tool_names_from_messages(msg_dicts)
            total_tokens = (session.get("input_tokens") or 0) + (session.get("output_tokens") or 0)

            if min_tokens > 0 and total_tokens < min_tokens:
                continue

            # Heuristic reason
            reason = _infer_mining_reason(
                session,
                tool_names=tool_names,
                has_prompt=bool(first_user),
                has_response=bool(last_assistant),
            )

            candidate = MinedCandidate.from_session_row(
                session,
                first_user,
                last_assistant,
                tool_names,
                reason=reason,
            )
            candidates.append(candidate)

    finally:
        if cursor_factory is None:
            conn.close()

    return MiningResult(
        source_name="state-db",
        candidates=candidates,
        total_sessions_scanned=total,
        total_candidates=len(candidates),
    )


# ---------------------------------------------------------------------------
# Trajectory file mining
# ---------------------------------------------------------------------------

def mine_from_trajectories(
    trajectories_path: str | Path,
    *,
    failed_only: bool = False,
    limit: int = 50,
) -> MiningResult:
    """Mine candidate eval cases from trajectory JSONL files.

    The trajectory format used by ``agent/trajectory.py``: one JSON object
    per line with keys ``conversations``, ``model``, ``completed``,
    ``timestamp``.
    """
    traj_path = Path(trajectories_path)
    if not traj_path.exists():
        logger.warning("Trajectory file not found at %s", traj_path)
        return MiningResult(source_name="trajectories", candidates=[], total_sessions_scanned=0, total_candidates=0)

    candidates: list[MinedCandidate] = []
    total_scanned = 0

    with traj_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping unparseable trajectory line in %s", traj_path)
                continue

            total_scanned += 1
            completed = entry.get("completed", True)

            if failed_only and completed:
                continue

            reason = "failed trajectory" if not completed else "trajectory sample"
            candidate = MinedCandidate.from_trajectory_entry(entry, reason=reason)
            candidates.append(candidate)

            if len(candidates) >= limit:
                break

    return MiningResult(
        source_name="trajectories",
        candidates=candidates,
        total_sessions_scanned=total_scanned,
        total_candidates=len(candidates),
    )


# ---------------------------------------------------------------------------
# Cron output mining
# ---------------------------------------------------------------------------

def mine_from_cron_outputs(
    cron_dir: str | Path,
    *,
    limit: int = 20,
    pattern: str = "*.md",
) -> MiningResult:
    """Mine candidate eval cases from cron output directories.

    Scans ``cron_dir/<job_id>/`` for the most recent ``.md`` output files
    and extracts the first user message (typically the cron prompt) and the
    last content block from each.
    """
    cron_path = Path(cron_dir)
    if not cron_path.is_dir():
        logger.warning("Cron output directory not found at %s", cron_path)
        return MiningResult(source_name="cron-outputs", candidates=[], total_sessions_scanned=0, total_candidates=0)

    candidates: list[MinedCandidate] = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    job_dirs = sorted(
        [d for d in cron_path.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )

    for job_dir in job_dirs:
        if len(candidates) >= limit:
            break

        # Find the most recent output file
        out_files = sorted(job_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if not out_files:
            continue

        latest = out_files[0]
        try:
            text = latest.read_text(encoding="utf-8")
        except OSError:
            continue

        # Extract the first significant content (skip skill preamble)
        # Heuristic: the cron prompt is typically at the very beginning or
        # just after the skill preamble.
        lines = text.splitlines()
        prompt = _extract_cron_prompt(lines)
        final_response = _extract_cron_final_response(lines)

        if not prompt and not final_response:
            continue

        job_id = job_dir.name
        candidate = MinedCandidate(
            candidate_id=f"mined.cron.{job_id}",
            source="cron-outputs",
            session_id=f"cron/{job_id}",
            model=None,
            provider=None,
            title=f"cron job {job_id}",
            prompt=prompt,
            context=None,
            final_response=final_response,
            tool_names=[],
            tool_call_count=0,
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=None,
            failed=False,
            reason="cron output sample",
            tags=["mined", "cron", "needs-review"],
            mined_at=now_iso,
        )
        candidates.append(candidate)

    return MiningResult(
        source_name="cron-outputs",
        candidates=candidates,
        total_sessions_scanned=len(job_dirs),
        total_candidates=len(candidates),
    )


# ---------------------------------------------------------------------------
# Conversion to draft eval case YAML
# ---------------------------------------------------------------------------

def candidate_to_draft_case(
    candidate: MinedCandidate,
    *,
    default_suite: str = "mined",
    default_task_type: str = "analysis",
) -> dict[str, Any]:
    """Convert a ``MinedCandidate`` into a YAML-serializable draft eval case dict.

    The returned dict is suitable for writing directly to a ``.yaml`` file
    for human review and later promotion to ``evals/cases/<suite>/``.
    """
    # Heuristic task type based on tool usage
    task_type = _heuristic_task_type(candidate.tool_names, candidate.prompt)

    # Build a human-readable title from the prompt first line
    title = candidate.title or _prompt_to_title(candidate.prompt)

    # Generate deterministic assertions from the observed tools
    assertions: list[dict[str, Any]] = []

    if candidate.tool_names:
        for tool_name in sorted(set(candidate.tool_names)):
            assertions.append(
                {
                    "kind": "tool_used",
                    "params": {"tool": tool_name},
                    "weight": 1.0,
                    "required": False,
                }
            )

    # Basic quality gates
    assertions.append(
        {"kind": "non_empty_output", "weight": 2.0, "required": True}
    )

    # Build tags
    tags = list(candidate.tags) if candidate.tags else []
    if candidate.failed:
        tags.append("regression")
    if "browser" in str(candidate.tool_names):
        tags.append("browser")
    if "web_search" in str(candidate.tool_names) or "web_extract" in str(candidate.tool_names):
        tags.append("web")
    tags = list(dict.fromkeys(tags))  # deduplicate preserving order

    reason = candidate.reason or ""
    notes = f"Mined from {candidate.source} session {candidate.session_id[:16]}"
    if reason:
        notes += f". Reason: {reason}"

    return {
        "case_id": candidate.candidate_id,
        "suite": default_suite,
        "task_type": task_type,
        "title": title,
        "prompt": candidate.prompt,
        "context": candidate.context or None,
        "tags": tags,
        "enabled_toolsets": _heuristic_toolsets(candidate.tool_names),
        "expected_tools": sorted(set(candidate.tool_names)),
        "forbidden_tools": [],
        "assertions": assertions,
        "judge_dimensions": [],
        "gold_answer": None,
        "notes": notes,
    }


def export_draft_cases(
    candidates: list[MinedCandidate],
    *,
    output_dir: str | Path,
    default_suite: str = "mined",
    prefix: str = "draft_",
) -> list[Path]:
    """Write each candidate as a standalone YAML draft case file.

    Returns the list of written file paths.
    """
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for candidate in candidates:
        draft = candidate_to_draft_case(candidate, default_suite=default_suite)
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", draft["case_id"])
        filename = f"{prefix}{safe_id}.yaml"
        file_path = out_root / filename

        yaml_bytes = yaml.safe_dump(
            draft,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        ).encode("utf-8")

        file_path.write_bytes(yaml_bytes)
        written.append(file_path)

    return written


def export_candidates_report(
    candidates: list[MinedCandidate],
    output_path: str | Path,
) -> Path:
    """Write a summary markdown report listing all mined candidates."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Mined eval case candidates",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Total candidates:** {len(candidates)}",
        "",
        "## Candidates",
        "",
        "| # | Candidate ID | Session | Model | Tools | Failed | Reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for idx, c in enumerate(candidates, start=1):
        tool_str = ", ".join(c.tool_names[:5])
        if len(c.tool_names) > 5:
            tool_str += " ..."
        session_short = c.session_id[:16] if c.session_id else "-"
        lines.append(
            f"| {idx} | {c.candidate_id} | {session_short} | {c.model or '-'} "
            f"| {tool_str or '-'} | {'❌' if c.failed else '✅'} | {c.reason or '-'} |"
        )

    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _first_user_message(messages: list[dict[str, Any]]) -> str:
    """Return the content of the first user message (not tool results)."""
    for msg in messages:
        role = msg.get("role", "")
        if role == "user":
            content = msg.get("content", "") or ""
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


def _last_assistant_message(messages: list[dict[str, Any]]) -> str:
    """Return the content of the last assistant message that has no tool_calls."""
    last_text = ""
    for msg in messages:
        role = msg.get("role", "")
        if role == "assistant":
            content = msg.get("content", "") or ""
            tc = msg.get("tool_calls")
            # Prefer final text-only responses (no tool calls)
            if isinstance(content, str) and content.strip() and not tc:
                last_text = content.strip()
            # Fallback: capture even empty text as long as it's final
            elif isinstance(content, str) and not tc:
                last_text = content.strip()
    return last_text


def _unique_tool_names_from_messages(messages: list[dict[str, Any]]) -> list[str]:
    """Extract unique tool names from assistant tool_calls in messages."""
    seen: set[str] = set()
    names: list[str] = []
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        raw_tc = msg.get("tool_calls")
        if not raw_tc or not isinstance(raw_tc, (list, str)):
            continue
        if isinstance(raw_tc, str):
            try:
                raw_tc = json.loads(raw_tc)
            except (json.JSONDecodeError, TypeError):
                continue
        for tc in raw_tc:
            if isinstance(tc, dict):
                func = tc.get("function", {})
                name = func.get("name", "") if isinstance(func, dict) else ""
                if not name:
                    name = tc.get("name", "")
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
    return names


def _unique_tool_names_from_conversations(conversations: list[dict[str, Any]]) -> list[str]:
    """Extract unique tool names from ShareGPT-format conversations."""
    seen: set[str] = set()
    names: list[str] = []
    for msg in conversations:
        if msg.get("role") != "assistant":
            continue
        raw_tc = msg.get("tool_calls")
        if not raw_tc or not isinstance(raw_tc, list):
            continue
        for tc in raw_tc:
            if isinstance(tc, dict):
                func = tc.get("function", {})
                name = func.get("name", "") if isinstance(func, dict) else ""
                if not name:
                    name = tc.get("name", "")
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
    return names


def _compute_elapsed_ms(session: dict[str, Any]) -> int | None:
    started = session.get("started_at")
    ended = session.get("ended_at")
    if started is not None and ended is not None:
        return int((ended - started) * 1000)
    return None


def _infer_mining_reason(
    session: dict[str, Any],
    *,
    tool_names: list[str],
    has_prompt: bool,
    has_response: bool,
) -> str | None:
    """Heuristic: why this session is worth mining."""
    end_reason = session.get("end_reason")

    if end_reason in ("error", "interrupted"):
        return f"session ended with {end_reason}"
    if end_reason == "branched":
        return "session was manually branched — likely interesting"
    if not has_response:
        return "no assistant response — possibly incomplete"
    if not has_prompt:
        return None  # no user input to build a prompt from
    if tool_names:
        return f"used {len(tool_names)} tool(s): {', '.join(tool_names[:3])}"
    return "completed session with direct response"


def _heuristic_task_type(tool_names: list[str], prompt: str) -> str:
    """Guess the task type from tool usage and prompt text."""
    prompt_lower = prompt.lower()

    if "browser" in str(tool_names) or "vision" in str(tool_names):
        if "browser_navigate" in tool_names or "browser_vision" in tool_names:
            return "browser"
        return "multimodal"
    if any(t in tool_names for t in ("web_search", "web_extract")):
        if "review" in prompt_lower or "analyse" in prompt_lower or "analyze" in prompt_lower or "audit" in prompt_lower:
            return "review"
        if (
            "brief" in prompt_lower
            or "summary" in prompt_lower
            or "summarize" in prompt_lower
            or "summarise" in prompt_lower
            or "report" in prompt_lower
        ):
            return "briefing"
        return "analysis"
    if "terminal" in tool_names or "execute_code" in tool_names:
        return "tooling"
    if "routing" in prompt_lower or "model" in prompt_lower or "provider" in prompt_lower:
        return "routing"
    return "analysis"


def _heuristic_toolsets(tool_names: list[str]) -> list[str]:
    """Infer required toolsets from tool names."""
    toolsets: list[str] = []
    if any(t in tool_names for t in ("web_search", "web_extract")):
        toolsets.append("web")
    if any(t in tool_names for t in ("browser_navigate", "browser_vision", "browser_click")):
        toolsets.append("browser")
    if any(t in tool_names for t in ("terminal",)):
        toolsets.append("terminal")
    if any(t in tool_names for t in ("execute_code",)):
        toolsets.append("code_execution")
    if any(t in tool_names for t in ("vision_analyze",)):
        toolsets.append("vision")
    if any(t in tool_names for t in ("delegate_task",)):
        toolsets.append("delegation")
    return toolsets


def _prompt_to_title(prompt: str) -> str:
    """Derive a short title from the first line or sentence of the prompt."""
    first_line = prompt.split("\n")[0].strip()
    # Take first ~80 chars
    if len(first_line) > 80:
        first_line = first_line[:77] + "..."
    return first_line or "Mined session"


def _extract_cron_prompt(lines: list[str]) -> str:
    """Extract the cron prompt from output lines.

    The first non-empty line that looks like a user instruction.
    """
    # Skip first few lines if they look like markdown headers or skill preambles
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("---"):
            continue
        if len(stripped) > 20:
            return stripped[:200]
    return ""


def _extract_cron_final_response(lines: list[str]) -> str:
    """Extract the final content block from a cron output file.

    Looks for the last substantial text block (not a preamble line).
    """
    # Find the last significant paragraph (non-empty, non-header, meaningful length)
    content_blocks: list[str] = []
    current: list[str] = []

    for line in reversed(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
            current.append(stripped)
        elif current:
            content_blocks.append(" ".join(reversed(current)))
            current = []
            if len(content_blocks) >= 3:
                break

    if current:
        content_blocks.append(" ".join(reversed(current)))

    # The last content block (reversed order) is the final section
    if content_blocks:
        result = content_blocks[0]
        if len(result) > 500:
            result = result[:497] + "..."
        return result
    return ""