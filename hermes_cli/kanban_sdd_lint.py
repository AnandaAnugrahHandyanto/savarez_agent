"""Kanban SDD consistency lint — read-only cross-artifact analysis (spec-kit P7).

Implements the spec-kit P7 pattern: a non-destructive consistency check across
a task's spec/plan/tasks body before implementation runs.  Never modifies any
task; returns a ``LintReport`` the caller surfaces to the user.

Grafted from github/spec-kit (MIT, commit 34ce661) pattern P7:
  templates/commands/analyze.md — STRICTLY READ-ONLY, runs after tasks before
  implement, findings categorised critical/high/medium/low.

Usage (programmatic)::

    from hermes_cli.kanban_sdd_lint import lint_task
    report = lint_task(task_id)
    for f in report.findings:
        print(f.severity, f.code, f.message)

Usage (CLI — wire via ``hermes kanban lint <id>``)::

    See hermes_cli/kanban.py for CLI registration.  The lint verb is read-only
    and safe to run at any point; it does not change task state.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from hermes_cli import kanban_db as kb


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "critical"   # blocks implementation — must be resolved first
    HIGH = "high"           # strongly recommended to fix
    MEDIUM = "medium"       # good practice
    LOW = "low"             # style / canonical-format
    INFO = "info"           # advisory only


@dataclass
class LintFinding:
    severity: Severity
    code: str
    message: str
    section: Optional[str] = None


@dataclass
class LintReport:
    task_id: str
    ok: bool                           # True iff no CRITICAL findings
    findings: list[LintFinding] = field(default_factory=list)

    def blocking(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == Severity.CRITICAL]

    def summary(self) -> str:
        if not self.findings:
            return f"{self.task_id}: OK — no findings"
        counts: dict[Severity, int] = {}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        parts = [f"{v} {k.value}" for k, v in counts.items()]
        return f"{self.task_id}: {', '.join(parts)}"


# ---------------------------------------------------------------------------
# Required SDD body sections (P1 spec vocabulary, from spec-kit P7)
# ---------------------------------------------------------------------------

_REQUIRED_SECTIONS: dict[str, tuple[Severity, str, str]] = {
    "Goal": (
        Severity.CRITICAL,
        "SDD001",
        "missing **Goal** section — spec has no user-facing outcome statement",
    ),
    "Acceptance criteria": (
        Severity.HIGH,
        "SDD002",
        "missing **Acceptance criteria** — no verifiable done conditions defined",
    ),
    "Approach": (
        Severity.MEDIUM,
        "SDD003",
        "missing **Approach** section — worker has no stated method or plan",
    ),
}

# Canonical P3 task line: - [ ] [ID] [P?] description (optional file path)
_CANONICAL_TASK_RE = re.compile(
    r"^- \[[ x]\] \[[A-Za-z0-9_.-]+\]",
    re.MULTILINE,
)

# Non-canonical: bare checkbox without [ID] prefix
_BARE_CHECKBOX_RE = re.compile(r"^- \[[ x]\] (?!\[)", re.MULTILINE)


# ---------------------------------------------------------------------------
# Individual lint checks
# ---------------------------------------------------------------------------

def _check_required_sections(body: str) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for section_name, (sev, code, msg) in _REQUIRED_SECTIONS.items():
        bold_heading = f"**{section_name}**"
        atx_heading = f"## {section_name}"
        if bold_heading not in body and atx_heading not in body:
            findings.append(LintFinding(sev, code, msg, section=section_name))
    return findings


def _check_task_format(body: str) -> list[LintFinding]:
    """Flag bare checkboxes (missing [ID]) as P3 format violations."""
    findings: list[LintFinding] = []
    bare = _BARE_CHECKBOX_RE.findall(body)
    if bare:
        count = len(bare)
        findings.append(LintFinding(
            Severity.LOW,
            "SDD004",
            f"{count} bare checkbox(es) missing [ID] — use canonical P3 format: "
            r"`- [ ] [T1] [P] description (file.py)` (spec-kit P3)",
            section="task-format",
        ))
    return findings


def _check_out_of_scope(body: str) -> list[LintFinding]:
    if "**Out of scope**" not in body and "## Out of scope" not in body:
        return [LintFinding(
            Severity.INFO,
            "SDD005",
            "no **Out of scope** section — consider making non-goals explicit "
            "to prevent scope creep",
        )]
    return []


def _check_stories_format(body: str) -> list[LintFinding]:
    """Advisory check: if Stories section exists, verify [P1]/[P2]/[P3] labels."""
    findings: list[LintFinding] = []
    if "**Stories**" not in body and "## Stories" not in body:
        return findings
    # Stories section present — check for at least one priority label
    if not re.search(r"\[P[123]\]", body):
        findings.append(LintFinding(
            Severity.MEDIUM,
            "SDD006",
            "**Stories** section present but no [P1]/[P2]/[P3] priority labels "
            "found — each story slice should be labeled by priority (P2)",
            section="Stories",
        ))
    return findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def lint_body(body: str, task_id: str = "<inline>") -> LintReport:
    """Lint a task body string without a DB lookup.

    Useful for testing and for linting draft bodies before they are persisted.
    """
    findings: list[LintFinding] = []
    findings.extend(_check_required_sections(body))
    findings.extend(_check_task_format(body))
    findings.extend(_check_out_of_scope(body))
    findings.extend(_check_stories_format(body))
    ok = not any(f.severity == Severity.CRITICAL for f in findings)
    return LintReport(task_id=task_id, ok=ok, findings=findings)


def lint_task(task_id: str) -> LintReport:
    """Load a task from the DB and lint its body. Read-only."""
    with kb.connect_closing() as conn:
        task = kb.get_task(conn, task_id)
    if task is None:
        return LintReport(
            task_id=task_id,
            ok=False,
            findings=[LintFinding(Severity.CRITICAL, "SDD000", "unknown task id")],
        )
    return lint_body(task.body or "", task_id=task_id)


def lint_tasks(task_ids: list[str]) -> list[LintReport]:
    """Lint multiple tasks; returns one report per id. Read-only."""
    return [lint_task(tid) for tid in task_ids]
