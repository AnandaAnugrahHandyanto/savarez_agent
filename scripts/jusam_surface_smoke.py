#!/usr/bin/env python3
"""Jusam (주삼) user-origin surface smoke closeout helper.

Closes out the **P0 interface smoke test** gate from the canonical operating
model: CLI already passes, but Slack/Desktop *user-origin* smoke is still
open. This is a *developer artifact*, not a pytest, that lets Seiyeong/Jusam:

  1. Extract the canonical smoke prompt + 11 pass criteria from the sywork
     operating-model doc (single source of truth, not hardcoded here).
  2. Compare response artifacts (plain-text files) against the 11 criteria
     using keyword heuristics (labelled ``heuristic`` unless an artifact
     override marks a criterion ``reviewed``).
  3. Locate Desktop / Slack response artifacts in ``~/.hermes/state.db`` after
     a *real* user-origin prompt, by marker — without faking user-origin
     Slack by bot-posting.
  4. Write a sywork canonical report, and optionally a Slack ``#90``-compatible
     thin summary, with redaction of secrets.
  5. Make ``blocked`` / ``preflight`` vs ``direct-user-origin`` explicit so a
     bot-origin or missing artifact is never mistaken for a user-origin pass.

Design for offline/dry use *and* real use later:
  - Runs with no live LLM by reading artifact files you capture by hand.
  - ``--no-post`` (default) never touches Slack; posting is opt-in only.
  - ``--dry-run`` prints the report to stdout instead of writing the file.

Usage
-----
    python scripts/jusam_surface_smoke.py --print-prompt

    python scripts/jusam_surface_smoke.py \
        --slack-artifact out/slack.txt \
        --desktop-artifact out/desktop.txt \
        --write-report --no-post

    # find candidate artifacts by marker in state.db (read-only)
    python scripts/jusam_surface_smoke.py --marker JUSAM-SMOKE-7f3a --find

Safety
------
  - Never prints or persists Slack tokens / OAuth URLs / credentials; all
    output is run through a redactor.
  - Never bot-posts a smoke prompt to fake user-origin Slack. Slack "direct"
    only ever reaches ``pass`` from an artifact you confirm is user-typed.
  - Read-only against ``state.db``; never restarts/stops/starts the gateway.
  - Stdlib only.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

# ── canonical locations ─────────────────────────────────────────────────────

CANONICAL_DOC = Path(
    "/Users/seiyeong/sywork/00-system/hermes/council/"
    "hermes-slack-desktop-notion-operating-model.md"
)
REPORT_DIR = Path("/Users/seiyeong/sywork/00-system/hermes/council")
REPORT_STEM = "jusam-quality-reproducibility-smoke"


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


def default_state_db() -> Path:
    return _hermes_home() / "state.db"


# ── redaction ───────────────────────────────────────────────────────────────

# Patterns that must never reach a report, Slack, or stdout.
_REDACT_PATTERNS = [
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]+"), "***REDACTED-SLACK-TOKEN***"),
    (re.compile(r"(?i)(SLACK_[A-Z_]*TOKEN\s*=\s*)\S+"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(SLACK_[A-Z_]*SECRET\s*=\s*)\S+"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(_API_KEY\s*=\s*)\S+"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(authorization:\s*bearer\s+)\S+"), r"\1***REDACTED***"),
    (re.compile(r"https://\S*oauth\S*"), "https://***REDACTED-OAUTH-URL***"),
    (re.compile(r"https://hooks\.slack\.com/\S+"), "https://***REDACTED-WEBHOOK***"),
    (re.compile(r"\bsk-[A-Za-z0-9-]{16,}\b"), "***REDACTED-KEY***"),
]


def redact(text: str) -> str:
    """Strip secrets/OAuth/webhook strings from any text before display."""
    out = text or ""
    for pattern, repl in _REDACT_PATTERNS:
        out = pattern.sub(repl, out)
    return out


# ── canonical doc parsing ───────────────────────────────────────────────────


class DocParseError(RuntimeError):
    pass


def extract_prompt(doc_text: str) -> str:
    """Return the fenced smoke-test prompt under '### Smoke-test prompt'."""
    m = re.search(
        r"###\s*Smoke-test prompt\s*\n+```[a-zA-Z]*\n(.*?)\n```",
        doc_text,
        re.DOTALL,
    )
    if not m:
        raise DocParseError("could not find '### Smoke-test prompt' fenced block")
    return m.group(1).strip()


def extract_criteria(doc_text: str) -> list[str]:
    """Return the bullet list under '### Pass criteria' (one per criterion)."""
    m = re.search(r"###\s*Pass criteria\s*\n(.*?)(?:\n##\s|\Z)", doc_text, re.DOTALL)
    if not m:
        raise DocParseError("could not find '### Pass criteria' section")
    block = m.group(1)
    criteria = [
        line[2:].strip()
        for line in block.splitlines()
        if line.startswith("- ")
    ]
    if not criteria:
        raise DocParseError("no '- ' bullet criteria found under Pass criteria")
    return criteria


# ── heuristic keyword matchers for the 11 criteria ──────────────────────────
#
# Each matcher is a list of "groups"; a criterion matches heuristically when
# EVERY group has at least one keyword present (case-insensitive, ASCII-folded
# loosely). This is intentionally a first-pass signal, always labelled
# ``heuristic`` in the report — semantic review can override per artifact.

CriterionMatcher = list[list[str]]

CRITERION_MATCHERS: list[CriterionMatcher] = [
    # 1. 세영 = EGNIS CSO / final decision-maker; not 대표.
    [["세영", "seyoung", "seiyeong"], ["cso", "최고전략", "전략책임"], ["결정", "decision", "판단"]],
    # 2. Hermes/주삼 = AI 비서실장 / AI Chief Office OS.
    [["주삼", "hermes"], ["비서실장", "chief office", "chief of staff", "비서실", "chief"]],
    # 3. Desktop/Slack/CLI are interfaces, not separate identities.
    [["interface", "인터페이스"], ["identity", "정체성", "별도", "separate", "같은 주삼", "same"]],
    # 4. Desktop=deep work; Slack=hot log; sywork=canonical; Notion=scan.
    [["desktop"], ["slack"], ["sywork"], ["notion"], ["canonical", "정본", "hot", "scan", "deep"]],
    # 5. Worker-first routing; Hermes verifies/synthesizes.
    [["claude", "codex", "worker"], ["worker-first", "먼저", "first", "draft", "실행"], ["verif", "검증", "synthes", "synthe", "최종"]],
    # 6. Decision Tier T0~T3 and gates understood.
    [["tier", "티어", "t0", "t1", "t2", "t3"], ["gate", "게이트", "승인", "approval", "escal"]],
    # 7. Completion is evidence-backed.
    [["evidence", "증거", "근거"], ["file", "diff", "test", "artifact", "tool", "cron", "파일", "산출물", "테스트", "검증"]],
    # 8. T2+ requires External Lens unless bypassed with reason.
    [["external lens", "외부 렌즈", "외부렌즈", "external"], ["t2", "전략", "pricing", "positioning", "market", "product"], ["bypass", "우회", "unless", "예외", "reason"]],
    # 9. EGNIS Context Intelligence Layer.
    [["egnis"], ["context intelligence", "intelligence layer", "context layer", "맥락", "intelligence"], ["meta", "cafe24", "d2c", "brand", "브랜드", "risk", "opportun", "signal", "리스크", "기회"]],
    # 10. Repeated misses -> violation log -> WARN/HARD after approval.
    [["violation", "위반", "misclass", "오분류"], ["log", "로그", "기록"], ["warn", "hard", "gate", "승인", "approval", "반복", "repeat"]],
    # 11. 세영 need not memorize tool/skill names; 주삼 routes.
    [["tool", "skill", "툴", "스킬", "이름", "name"], ["외울 필요", "외우", "memoriz", "memorize", "라우팅", "rout"]],
]


def _fold(text: str) -> str:
    return (text or "").lower()


def match_criterion(matcher: CriterionMatcher, text: str) -> tuple[bool, list[int]]:
    """Return (matched, indices_of_missing_groups) for one criterion."""
    folded = _fold(text)
    missing: list[int] = []
    for idx, group in enumerate(matcher):
        if not any(kw in folded for kw in group):
            missing.append(idx)
    return (not missing, missing)


# ── artifact override directives ────────────────────────────────────────────
#
# An artifact file may begin with directive lines so a human can override the
# heuristic after semantic review, e.g.:
#
#   #smoke: reviewed
#   #smoke: origin=user
#   #smoke: criterion 8 = pass  (External Lens explained in §X)
#
# Directives are stripped from the body before keyword matching.

_DIRECTIVE_RE = re.compile(r"^\s*#smoke:\s*(.*)$", re.IGNORECASE)
_CRIT_OVERRIDE_RE = re.compile(
    r"criterion\s+(\d+)\s*=\s*(pass|fail|warn)(?:\s*\((.*)\))?", re.IGNORECASE
)


@dataclass
class ArtifactDirectives:
    reviewed: bool = False
    origin: Optional[str] = None  # "user" | "bot" | None
    criterion_overrides: dict[int, tuple[str, str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def parse_artifact(raw: str) -> tuple[str, ArtifactDirectives]:
    """Split directive header lines from the response body."""
    directives = ArtifactDirectives()
    body_lines: list[str] = []
    for line in raw.splitlines():
        m = _DIRECTIVE_RE.match(line)
        if not m:
            body_lines.append(line)
            continue
        cmd = m.group(1).strip()
        low = cmd.lower()
        if low == "reviewed":
            directives.reviewed = True
        elif low.startswith("origin"):
            val = low.split("=", 1)[-1].strip() if "=" in low else ""
            directives.origin = val or None
        elif _CRIT_OVERRIDE_RE.search(cmd):
            cm = _CRIT_OVERRIDE_RE.search(cmd)
            assert cm
            directives.criterion_overrides[int(cm.group(1))] = (
                cm.group(2).lower(),
                (cm.group(3) or "").strip(),
            )
        else:
            directives.notes.append(cmd)
    return ("\n".join(body_lines).strip(), directives)


# ── evaluation model ────────────────────────────────────────────────────────


@dataclass
class CriterionResult:
    number: int
    text: str
    status: str  # "pass" | "fail"
    method: str  # "heuristic" | "reviewed"
    note: str = ""


@dataclass
class SurfaceResult:
    surface: str  # "Slack direct" | "Desktop direct" | "CLI"
    state: str  # "pass" | "warn" | "blocked" | "fail"
    origin: str  # "direct-user-origin" | "bot-origin" | "preflight-blocked" | "artifact-missing"
    criteria: list[CriterionResult] = field(default_factory=list)
    note: str = ""

    @property
    def passed(self) -> int:
        return sum(1 for c in self.criteria if c.status == "pass")

    @property
    def total(self) -> int:
        return len(self.criteria)


def evaluate_artifact(
    surface: str,
    raw: Optional[str],
    criteria: list[str],
    *,
    allow_user_origin: bool,
) -> SurfaceResult:
    """Evaluate one surface against the 11 criteria.

    ``allow_user_origin`` distinguishes a surface where we can actually assert
    user-origin (Desktop/CLI via state.db role=user, or an artifact marked
    ``origin=user``) from Slack, where a bot-posted message is NOT user-origin.
    """
    if raw is None:
        return SurfaceResult(
            surface=surface,
            state="blocked",
            origin="artifact-missing",
            note="no artifact supplied — surface smoke not closed",
        )

    body, directives = parse_artifact(raw)

    # Origin classification. An explicit '#smoke: origin=' directive is the
    # human's confirmation and always wins. Absent a directive, only surfaces
    # that can intrinsically assert user-origin (allow_user_origin=True, e.g.
    # Desktop/CLI via state.db role=user) default to direct-user-origin; Slack
    # defaults to bot-origin so an unconfirmed/bot-posted message never passes.
    origin = "direct-user-origin"
    note = ""
    if directives.origin == "user":
        origin = "direct-user-origin"
    elif directives.origin == "bot":
        origin = "bot-origin"
        note = "artifact marked bot-origin — NOT user-origin; cannot pass direct"
    elif not allow_user_origin:
        origin = "bot-origin"  # default-safe: unconfirmed Slack is not user-origin
        note = (
            "origin unconfirmed — defaulting to bot-origin (not a user-origin "
            "pass). Add '#smoke: origin=user' only for a genuinely user-typed "
            "prompt/response (never bot-posted to fake Slack user-origin)."
        )

    results: list[CriterionResult] = []
    for i, crit_text in enumerate(criteria):
        number = i + 1
        matcher = CRITERION_MATCHERS[i] if i < len(CRITERION_MATCHERS) else []
        override = directives.criterion_overrides.get(number)
        if override:
            status_raw, ovr_note = override
            status = "pass" if status_raw == "pass" else "fail"
            results.append(
                CriterionResult(
                    number=number,
                    text=crit_text,
                    status=status,
                    method="reviewed",
                    note=ovr_note or "human override",
                )
            )
            continue

        matched, missing = match_criterion(matcher, body) if matcher else (False, [])
        method = "reviewed" if directives.reviewed else "heuristic"
        if matcher:
            crit_note = (
                "keyword signal present"
                if matched
                else f"missing keyword group(s): {missing}"
            )
        else:
            crit_note = "no matcher defined; manual review required"
        results.append(
            CriterionResult(
                number=number,
                text=crit_text,
                status="pass" if matched else "fail",
                method=method,
                note=crit_note,
            )
        )

    n_pass = sum(1 for c in results if c.status == "pass")
    n_total = len(results)

    # State: a Slack bot-origin artifact can never be "pass" no matter the
    # keyword coverage. User-origin surfaces pass only on full coverage.
    if origin == "bot-origin":
        state = "warn"
        if not note:
            note = "bot-origin: criteria coverage shown for reference only"
    elif n_pass == n_total:
        state = "pass"
    elif n_pass >= max(1, n_total - 2):
        state = "warn"
        note = note or f"{n_total - n_pass} criterion(s) unmet (heuristic)"
    else:
        state = "fail"
        note = note or f"{n_total - n_pass} criterion(s) unmet (heuristic)"

    return SurfaceResult(
        surface=surface, state=state, origin=origin, criteria=results, note=note
    )


# ── state.db locating (read-only) ───────────────────────────────────────────


@dataclass
class DbCandidate:
    session_id: str
    source: str
    role: str
    surface: str  # "Desktop" | "Slack" | "CLI" | "?"
    timestamp: float
    snippet: str
    relation: str = "marker"  # "marker" | "following-assistant"


def _active_clause(conn: sqlite3.Connection) -> str:
    """``" AND m.active = 1"`` when the messages table tracks soft-deletes.

    The live Hermes schema soft-deletes rewound/edited rows via ``active`` (1 =
    live, 0 = superseded). Filtering on it keeps the closeout pinned to the
    *current* user-origin exchange instead of a stale/rewound one. Older or test
    schemas without the column get an empty clause so queries still run. The
    returned fragment is a constant — no user input — so it is injection-safe.
    """
    try:
        cols = conn.execute("PRAGMA table_info(messages)").fetchall()
    except sqlite3.Error:
        return ""
    names = {(c["name"] if isinstance(c, sqlite3.Row) else c[1]) for c in cols}
    return " AND m.active = 1" if "active" in names else ""


def classify_source(source: str) -> str:
    s = (source or "").lower()
    if s == "tui":
        return "Desktop"
    if "slack" in s or "gateway" in s:
        return "Slack"
    if s == "cli":
        return "CLI"
    return "?"


def _row_to_candidate(r: sqlite3.Row, *, relation: str) -> DbCandidate:
    content = r["content"] or ""
    snippet = redact(content.strip().replace("\n", " "))[:160]
    return DbCandidate(
        session_id=r["session_id"],
        source=r["source"],
        role=r["role"],
        surface=classify_source(r["source"]),
        timestamp=float(r["timestamp"] or 0.0),
        snippet=snippet,
        relation=relation,
    )


def _following_assistant_rows(
    conn: sqlite3.Connection,
    session_id: str,
    after_ts: float,
    after_id: int,
    *,
    limit: int,
) -> list[sqlite3.Row]:
    """Assistant rows in the same session that follow a marker message.

    Stops at the next ``role=user`` message (the exchange boundary) so we pair a
    user-origin marker only with the assistant response(s) it actually produced.
    Non-user / non-assistant rows (tool, system) are skipped without breaking.
    """
    rows = conn.execute(
        f"""
        SELECT m.id, m.session_id, m.role, m.content, m.timestamp, s.source
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE m.session_id = ?
          AND (m.timestamp > ? OR (m.timestamp = ? AND m.id > ?))
          {_active_clause(conn)}
        ORDER BY m.timestamp ASC, m.id ASC
        """,
        (session_id, after_ts, after_ts, after_id),
    ).fetchall()
    out: list[sqlite3.Row] = []
    for r in rows:
        if r["role"] == "user":
            break  # next user turn ends this exchange
        if r["role"] == "assistant":
            out.append(r)
            if len(out) >= limit:
                break
    return out


def find_candidates(
    db_path: Path, marker: str, *, limit: int = 50, max_following: int = 4
) -> list[DbCandidate]:
    """Read-only search of state.db for messages containing ``marker``.

    Classifies source=tui as Desktop, source containing slack/gateway as Slack,
    cli as CLI. For every ``role=user`` marker hit it ALSO appends the next
    assistant message(s) in the same session — even when that assistant response
    does not itself contain the marker — so the response artifact can be located
    from a real user-origin prompt.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"state.db not found: {db_path}")
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT m.id, m.session_id, m.role, m.content, m.timestamp, s.source
            FROM messages m
            JOIN sessions s ON s.id = m.session_id
            WHERE m.content LIKE ?
              {_active_clause(conn)}
            ORDER BY m.timestamp ASC, m.id ASC
            LIMIT ?
            """,
            (f"%{marker}%", limit),
        ).fetchall()

        out: list[DbCandidate] = []
        seen_ids: set[int] = set()
        for r in rows:
            if r["id"] in seen_ids:
                continue
            seen_ids.add(r["id"])
            out.append(_row_to_candidate(r, relation="marker"))
            # Only a real role=user marker is treated as user-origin; pair it
            # with the assistant response that followed it in the same session.
            if r["role"] == "user":
                for f in _following_assistant_rows(
                    conn, r["session_id"], r["timestamp"], r["id"], limit=max_following
                ):
                    if f["id"] in seen_ids:
                        continue
                    seen_ids.add(f["id"])
                    out.append(_row_to_candidate(f, relation="following-assistant"))
    finally:
        conn.close()
    return out


# ── state.db artifact extraction by surface ─────────────────────────────────


@dataclass
class SurfaceArtifact:
    surface: str  # "Desktop" | "Slack" | "CLI" | "?"
    session_id: str
    source: str
    timestamp: float
    user_snippet: str  # redacted snippet of the user-origin marker message
    assistant_text: str  # redacted following assistant content (the artifact)
    user_origin: bool = True
    note: str = ""


def extract_state_db_artifacts(
    db_path: Path, marker: str, *, max_following: int = 4
) -> dict[str, SurfaceArtifact]:
    """Latest response artifact per surface for a user-origin ``marker``.

    Only ``role=user`` messages are treated as user-origin markers. Each such
    marker is paired with the following assistant content in the SAME session —
    the assistant text need not contain the marker. Sources map to surfaces via
    :func:`classify_source` (tui→Desktop, slack/gateway→Slack, cli→CLI). When a
    surface has several qualifying exchanges, the most recent (by marker
    timestamp) wins. Slack artifacts carry a default-safe note: a genuine
    role=user marker from a slack/gateway source is user-origin, but it must not
    be a bot-posted message.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"state.db not found: {db_path}")
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        markers = conn.execute(
            f"""
            SELECT m.id, m.session_id, m.role, m.content, m.timestamp, s.source
            FROM messages m
            JOIN sessions s ON s.id = m.session_id
            WHERE m.content LIKE ? AND m.role = 'user'
              {_active_clause(conn)}
            ORDER BY m.timestamp ASC, m.id ASC
            """,
            (f"%{marker}%",),
        ).fetchall()

        by_surface: dict[str, SurfaceArtifact] = {}
        for mk in markers:
            following = _following_assistant_rows(
                conn, mk["session_id"], mk["timestamp"], mk["id"], limit=max_following
            )
            if not following:
                continue  # user-origin marker with no assistant response — skip
            assistant_text = "\n".join((f["content"] or "") for f in following).strip()
            if not assistant_text:
                continue
            surface = classify_source(mk["source"])
            note = ""
            if surface == "Slack":
                note = (
                    "slack/gateway role=user marker — genuine user-origin; must "
                    "NOT be a bot-posted message"
                )
            art = SurfaceArtifact(
                surface=surface,
                session_id=mk["session_id"],
                source=mk["source"],
                timestamp=float(mk["timestamp"] or 0.0),
                user_snippet=redact(
                    (mk["content"] or "").strip().replace("\n", " ")
                )[:160],
                assistant_text=redact(assistant_text),
                user_origin=True,
                note=note,
            )
            prev = by_surface.get(surface)
            if prev is None or art.timestamp >= prev.timestamp:
                by_surface[surface] = art
    finally:
        conn.close()
    return by_surface


def artifact_raw_from_state(art: SurfaceArtifact) -> str:
    """Render a :class:`SurfaceArtifact` as a raw artifact for evaluation.

    A state.db ``role=user`` marker is a genuine user-origin signal, so the
    artifact is stamped ``#smoke: origin=user`` — including for Slack, where the
    marker came from a slack/gateway source (never a bot post). Provenance and
    the Slack not-bot-origin caveat are preserved as ``#smoke:`` note lines.
    """
    lines = ["#smoke: origin=user"]
    lines.append(
        f"#smoke: from state.db session={art.session_id[:12]} "
        f"source={redact(art.source)}"
    )
    if art.note:
        lines.append(f"#smoke: {art.note}")
    lines.append(art.assistant_text)
    return "\n".join(lines)


# ── report rendering ────────────────────────────────────────────────────────

_STATE_EMOJI = {"pass": "✅", "warn": "⚠️", "blocked": "⛔", "fail": "❌"}


def _today(stamp: Optional[float]) -> str:
    t = time.localtime(stamp) if stamp is not None else time.localtime()
    return time.strftime("%Y-%m-%d", t)


def render_report(
    surfaces: list[SurfaceResult],
    prompt: str,
    *,
    date_str: str,
    db_note: str = "",
) -> str:
    lines: list[str] = []
    lines.append(f"# 주삼 surface smoke 재현성/품질 closeout — {date_str}")
    lines.append("")
    lines.append(
        "> 생성: `scripts/jusam_surface_smoke.py` · 정본 기준: "
        "`hermes-slack-desktop-notion-operating-model.md` §7"
    )
    lines.append(
        "> user-origin 직접 통과와 preflight/blocked/bot-origin을 명시 구분한다. "
        "bot-origin 메시지는 Slack direct pass로 인정하지 않는다."
    )
    lines.append("")

    # Matrix.
    lines.append("## Surface matrix")
    lines.append("")
    lines.append("| Surface | State | Origin | Criteria pass | Note |")
    lines.append("|---|---|---|---:|---|")
    for s in surfaces:
        emoji = _STATE_EMOJI.get(s.state, "")
        crit = f"{s.passed}/{s.total}" if s.total else "—"
        note = redact(s.note).replace("|", "\\|")
        lines.append(
            f"| {s.surface} | {emoji} {s.state} | {s.origin} | {crit} | {note} |"
        )
    lines.append("")
    if db_note:
        lines.append(f"_state.db: {redact(db_note)}_")
        lines.append("")

    # Per-criterion detail.
    for s in surfaces:
        lines.append(f"## {s.surface} — 11 criteria")
        lines.append("")
        lines.append(f"- state: **{s.state}** · origin: **{s.origin}**")
        if s.note:
            lines.append(f"- note: {redact(s.note)}")
        lines.append("")
        if not s.criteria:
            lines.append("_no artifact evaluated_")
            lines.append("")
            continue
        lines.append("| # | Criterion | Result | Method | Semantic note |")
        lines.append("|---:|---|---|---|---|")
        for c in s.criteria:
            mark = "✅" if c.status == "pass" else "❌"
            ctext = redact(c.text).replace("|", "\\|")
            cnote = redact(c.note).replace("|", "\\|")
            lines.append(
                f"| {c.number} | {ctext} | {mark} {c.status} | {c.method} | {cnote} |"
            )
        lines.append("")

    # Canonical prompt appendix.
    lines.append("## Canonical smoke prompt (정본 §7)")
    lines.append("")
    lines.append("```text")
    lines.append(prompt)
    lines.append("```")
    lines.append("")
    lines.append("## Closeout 판정")
    lines.append("")
    closed = [s for s in surfaces if s.state == "pass" and s.origin == "direct-user-origin"]
    open_ = [s for s in surfaces if s not in closed]
    if closed:
        lines.append("**user-origin direct pass:** " + ", ".join(s.surface for s in closed))
    if open_:
        lines.append(
            "**미완 (artifact 필요 / bot-origin / heuristic 미달):** "
            + ", ".join(f"{s.surface}({s.state})" for s in open_)
        )
    lines.append("")
    return "\n".join(lines)


def render_slack_summary(surfaces: list[SurfaceResult], date_str: str) -> str:
    """Thin #90-compatible summary (links/state only; no raw transcript)."""
    parts = [f"*주삼 surface smoke {date_str}*"]
    for s in surfaces:
        emoji = _STATE_EMOJI.get(s.state, "")
        crit = f"{s.passed}/{s.total}" if s.total else "—"
        parts.append(f"{emoji} {s.surface}: {s.state} ({s.origin}) — {crit}")
    parts.append("_user-origin 직접 통과만 pass로 인정. bot-origin/누락은 미완._")
    return redact("\n".join(parts))


# ── CLI ─────────────────────────────────────────────────────────────────────


def _read(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"artifact not found: {p}")
    return p.read_text(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Jusam user-origin surface smoke closeout helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--doc", default=str(CANONICAL_DOC), help="canonical operating-model doc")
    ap.add_argument("--print-prompt", action="store_true", help="print the canonical smoke prompt and exit")
    ap.add_argument("--print-criteria", action="store_true", help="print the 11 pass criteria and exit")

    ap.add_argument("--slack-artifact", help="Slack response artifact (text file)")
    ap.add_argument("--desktop-artifact", help="Desktop response artifact (text file)")
    ap.add_argument("--cli-artifact", help="CLI response artifact (text file)")
    ap.add_argument("--include-cli", action="store_true", help="include a CLI row even without artifact")

    ap.add_argument("--marker", help="unique marker to locate artifacts in state.db")
    ap.add_argument("--find", action="store_true", help="search state.db for --marker (read-only) and print candidates")
    ap.add_argument(
        "--from-state-db",
        action="store_true",
        help=(
            "fill slack/desktop/cli artifacts from state.db where a real "
            "role=user marker + following assistant response exists (read-only)"
        ),
    )
    ap.add_argument("--state-db", default=str(default_state_db()), help="path to state.db")

    ap.add_argument("--write-report", action="store_true", help="write the sywork report file")
    ap.add_argument("--report-path", help="override report output path")
    ap.add_argument("--dry-run", action="store_true", help="print report to stdout instead of writing")

    ap.add_argument("--slack-summary", action="store_true", help="emit a #90-compatible Slack summary")
    ap.add_argument("--no-post", action="store_true", default=True, help="never post to Slack (default; posting is unsupported here)")
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    doc_path = Path(args.doc)
    try:
        doc_text = doc_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read canonical doc: {exc}", file=sys.stderr)
        return 2

    try:
        prompt = extract_prompt(doc_text)
        criteria = extract_criteria(doc_text)
    except DocParseError as exc:
        print(f"ERROR: doc parse failed: {exc}", file=sys.stderr)
        return 2

    if len(criteria) != len(CRITERION_MATCHERS):
        print(
            f"WARN: parsed {len(criteria)} criteria but {len(CRITERION_MATCHERS)} "
            "matchers are defined; heuristics may be misaligned.",
            file=sys.stderr,
        )

    if args.print_prompt:
        print(prompt)
        return 0

    if args.print_criteria:
        for i, c in enumerate(criteria, 1):
            print(f"{i:2d}. {c}")
        return 0

    # state.db candidate search (read-only).
    if args.find:
        if not args.marker:
            print("ERROR: --find requires --marker", file=sys.stderr)
            return 2
        try:
            cands = find_candidates(Path(args.state_db), args.marker)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        if not cands:
            print(f"no messages matching marker {args.marker!r} in {args.state_db}")
            return 1
        print(f"candidates for marker {args.marker!r} ({len(cands)}):")
        for c in cands:
            origin_hint = "user-origin candidate" if c.role == "user" else f"role={c.role}"
            slack_warn = ""
            if c.surface == "Slack" and c.role == "user":
                slack_warn = "  [verify NOT bot-posted before claiming user-origin]"
            print(
                f"  [{c.surface}] source={c.source} {origin_hint} "
                f"session={c.session_id[:12]} :: {c.snippet}{slack_warn}"
            )
        return 0

    # Evaluate surfaces against artifacts.
    surfaces: list[SurfaceResult] = []
    slack_raw = _read(args.slack_artifact)
    desktop_raw = _read(args.desktop_artifact)
    cli_raw = _read(args.cli_artifact)

    # Optionally backfill missing artifacts from state.db. Only a real role=user
    # marker paired with a following assistant response qualifies. Slack stays
    # default-safe: absent such a genuine user-origin marker it is never filled
    # (and never bot-posted to fake one).
    db_note = ""
    if args.from_state_db:
        if not args.marker:
            print("ERROR: --from-state-db requires --marker", file=sys.stderr)
            return 2
        try:
            db_arts = extract_state_db_artifacts(Path(args.state_db), args.marker)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        filled: list[str] = []
        if slack_raw is None and "Slack" in db_arts:
            slack_raw = artifact_raw_from_state(db_arts["Slack"])
            filled.append("Slack")
        if desktop_raw is None and "Desktop" in db_arts:
            desktop_raw = artifact_raw_from_state(db_arts["Desktop"])
            filled.append("Desktop")
        if cli_raw is None and "CLI" in db_arts:
            cli_raw = artifact_raw_from_state(db_arts["CLI"])
            filled.append("CLI")
        db_note = (
            "filled from state.db user-origin marker+assistant: "
            + ", ".join(filled)
            if filled
            else f"no user-origin marker+assistant pair for {args.marker!r} in state.db"
        )

    surfaces.append(
        evaluate_artifact("Slack direct", slack_raw, criteria, allow_user_origin=False)
    )
    surfaces.append(
        evaluate_artifact("Desktop direct", desktop_raw, criteria, allow_user_origin=True)
    )
    if cli_raw is not None or args.include_cli:
        surfaces.append(
            evaluate_artifact("CLI", cli_raw, criteria, allow_user_origin=True)
        )

    date_str = _today(None)
    report = render_report(surfaces, prompt, date_str=date_str, db_note=db_note)

    if args.slack_summary:
        print("=== Slack #90 summary (not posted) ===")
        print(render_slack_summary(surfaces, date_str))
        print("=== end summary ===\n")

    if args.write_report or args.dry_run:
        if args.dry_run:
            print(report)
        else:
            out_path = (
                Path(args.report_path)
                if args.report_path
                else REPORT_DIR / f"{REPORT_STEM}-{date_str}.md"
            )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(report, encoding="utf-8")
            print(f"report written: {out_path}")
    else:
        # Default: concise matrix to stdout.
        for s in surfaces:
            emoji = _STATE_EMOJI.get(s.state, "")
            crit = f"{s.passed}/{s.total}" if s.total else "—"
            print(f"{emoji} {s.surface}: {s.state} [{s.origin}] {crit}")
        print("(use --write-report to persist, --dry-run to preview the full report)")

    # Exit code: 0 only if EVERY surface in the matrix (including blocked /
    # artifact-missing ones) is a confirmed user-origin pass. A missing Slack
    # or Desktop artifact keeps the closeout open -> non-zero.
    all_pass = bool(surfaces) and all(
        s.state == "pass" and s.origin == "direct-user-origin" for s in surfaces
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
