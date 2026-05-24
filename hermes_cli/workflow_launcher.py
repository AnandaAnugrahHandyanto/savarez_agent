"""Workflow launcher for Codex to Claude alignment gates.

The launcher creates a small, file-backed operating shell inside a target
repository. Linear remains a coordination surface; the local `.workflow`
folder is the evidence-bearing source of truth.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from hermes_constants import get_hermes_home


WORKFLOW_DIRNAME = ".workflow"
STATE_FILENAME = "state.json"
EXPECTED_ARTIFACT_FILES = (
    "preview.html",
    "metadata.json",
    "artifact.md",
    "notes.md",
    "thumbnail.png",
)
SOURCE_FILES = ("source.html", "source.jsx", "source.fixed.jsx", "source.tsx")
GATE_STATUSES = frozenset({"pending", "ready", "blocked", "done", "skipped"})
VERIFY_RESULTS = frozenset({"passed", "failed", "blocked"})
GATE_DEFINITIONS = (
    ("scope_packet", "Scope packet", "Codex", "ARCHITECT_PACK.md"),
    ("codex_plan", "Codex plan", "Codex", "CODEX_PLAN.md"),
    ("claude_review", "Claude adversarial review", "Claude Code", "CLAUDE_CRITIQUE.md"),
    ("reconciliation", "Reconciliation", "Codex", "RECONCILIATION.md"),
    ("alignment_decision", "Alignment decision", "Codex + Claude", "ALIGNMENT_DECISION.md"),
    ("build", "Build", "Codex", "repo diff"),
    ("verification", "Verification", "Codex", "VERIFY.md"),
    ("linear_update", "Linear update", "Operator", "linear/LINEAR_ISSUE_TEMPLATE.md"),
)


@dataclass(frozen=True)
class ArtifactRecord:
    slug: str
    title: str
    updated_at: str
    missing: tuple[str, ...]
    source_file: str | None


@dataclass(frozen=True)
class ArtifactInventory:
    repo: Path
    total: int
    with_preview: int
    with_thumbnail: int
    missing_required_count: int
    records: tuple[ArtifactRecord, ...]


@dataclass(frozen=True)
class WorkflowWrite:
    path: Path
    action: str


@dataclass(frozen=True)
class WorkflowGate:
    key: str
    title: str
    owner: str
    status: str
    evidence: str
    note: str
    updated_at: str


@dataclass(frozen=True)
class VerificationRecord:
    command: str
    result: str
    note: str
    ran_at: str


@dataclass(frozen=True)
class WorkflowState:
    schema_version: int
    workflow_name: str
    repo: str
    created_at: str
    updated_at: str
    linear_issue: str | None
    linear_project: str | None
    gates: tuple[WorkflowGate, ...]
    verifications: tuple[VerificationRecord, ...]


def default_artifact_repository() -> Path:
    return get_hermes_home() / "artifact-repository"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _state_path(repo: Path) -> Path:
    return repo / WORKFLOW_DIRNAME / STATE_FILENAME


def _state_lock_path(repo: Path) -> Path:
    return repo / WORKFLOW_DIRNAME / ".state.lock"


@contextmanager
def _workflow_state_lock(repo: Path):
    lock_path = _state_lock_path(repo)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 10
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > 60:
                    lock_path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for workflow state lock: {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(
        f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp"
    )
    try:
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def _gate_to_dict(gate: WorkflowGate) -> dict[str, str]:
    return {
        "key": gate.key,
        "title": gate.title,
        "owner": gate.owner,
        "status": gate.status,
        "evidence": gate.evidence,
        "note": gate.note,
        "updated_at": gate.updated_at,
    }


def _verification_to_dict(record: VerificationRecord) -> dict[str, str]:
    return {
        "command": record.command,
        "result": record.result,
        "note": record.note,
        "ran_at": record.ran_at,
    }


def _state_to_dict(state: WorkflowState) -> dict:
    return {
        "schema_version": state.schema_version,
        "workflow_name": state.workflow_name,
        "repo": state.repo,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "linear_issue": state.linear_issue,
        "linear_project": state.linear_project,
        "gates": [_gate_to_dict(gate) for gate in state.gates],
        "verifications": [
            _verification_to_dict(record) for record in state.verifications
        ],
    }


def _gate_from_dict(data: dict) -> WorkflowGate:
    return WorkflowGate(
        key=str(data.get("key") or ""),
        title=str(data.get("title") or ""),
        owner=str(data.get("owner") or ""),
        status=str(data.get("status") or "pending"),
        evidence=str(data.get("evidence") or ""),
        note=str(data.get("note") or ""),
        updated_at=str(data.get("updated_at") or "Unknown"),
    )


def _verification_from_dict(data: dict) -> VerificationRecord:
    return VerificationRecord(
        command=str(data.get("command") or ""),
        result=str(data.get("result") or "blocked"),
        note=str(data.get("note") or ""),
        ran_at=str(data.get("ran_at") or "Unknown"),
    )


def _state_from_dict(data: dict) -> WorkflowState:
    gates = tuple(
        _gate_from_dict(item)
        for item in data.get("gates", [])
        if isinstance(item, dict)
    )
    verifications = tuple(
        _verification_from_dict(item)
        for item in data.get("verifications", [])
        if isinstance(item, dict)
    )
    return WorkflowState(
        schema_version=int(data.get("schema_version") or 1),
        workflow_name=str(data.get("workflow_name") or "Workflow"),
        repo=str(data.get("repo") or ""),
        created_at=str(data.get("created_at") or "Unknown"),
        updated_at=str(data.get("updated_at") or "Unknown"),
        linear_issue=data.get("linear_issue")
        if isinstance(data.get("linear_issue"), str)
        else None,
        linear_project=data.get("linear_project")
        if isinstance(data.get("linear_project"), str)
        else None,
        gates=gates,
        verifications=verifications,
    )


def _initial_state(
    repo: Path,
    workflow_name: str,
    linear_issue: str | None,
    linear_project: str | None,
    claude_gate_note: str | None,
) -> WorkflowState:
    now = _utc_now()
    gates = []
    for key, title, owner, evidence in GATE_DEFINITIONS:
        note = ""
        status = "pending"
        if key == "scope_packet":
            status = "ready"
            note = "Generated by workflow launcher."
        elif key == "claude_review" and claude_gate_note:
            note = claude_gate_note
        gates.append(
            WorkflowGate(
                key=key,
                title=title,
                owner=owner,
                status=status,
                evidence=evidence,
                note=note,
                updated_at=now,
            )
        )
    return WorkflowState(
        schema_version=1,
        workflow_name=workflow_name,
        repo=str(repo),
        created_at=now,
        updated_at=now,
        linear_issue=linear_issue,
        linear_project=linear_project,
        gates=tuple(gates),
        verifications=(),
    )


def load_workflow_state(repo: Path) -> WorkflowState | None:
    path = _state_path(repo.expanduser().resolve())
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _state_from_dict(data) if isinstance(data, dict) else None


def _write_workflow_state(repo: Path, state: WorkflowState) -> None:
    path = _state_path(repo)
    _write_text_atomic(
        path,
        json.dumps(_state_to_dict(state), indent=2, sort_keys=True) + "\n",
    )


def _read_metadata(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _record_updated_at(artifact_dir: Path, metadata: dict) -> str:
    for key in ("updated_at", "updatedAt", "created_at", "createdAt"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    latest = 0.0
    for child in artifact_dir.iterdir():
        if child.is_file():
            latest = max(latest, child.stat().st_mtime)
    if latest:
        return datetime.fromtimestamp(latest, timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    return "Unknown"


def inventory_artifact_repository(repo: Path, limit: int = 12) -> ArtifactInventory:
    repo = repo.expanduser().resolve()
    artifacts_dir = repo / "artifacts"
    records: list[ArtifactRecord] = []

    if artifacts_dir.exists():
        for artifact_dir in sorted(artifacts_dir.iterdir()):
            if not artifact_dir.is_dir():
                continue
            metadata = _read_metadata(artifact_dir / "metadata.json")
            title = str(metadata.get("title") or metadata.get("name") or artifact_dir.name)
            missing = [
                expected
                for expected in EXPECTED_ARTIFACT_FILES
                if not (artifact_dir / expected).exists()
            ]
            source_file = next(
                (candidate for candidate in SOURCE_FILES if (artifact_dir / candidate).exists()),
                None,
            )
            if source_file is None:
                missing.append("source.html|source.jsx")
            records.append(
                ArtifactRecord(
                    slug=artifact_dir.name,
                    title=title,
                    updated_at=_record_updated_at(artifact_dir, metadata),
                    missing=tuple(missing),
                    source_file=source_file,
                )
            )

    records.sort(key=lambda item: item.updated_at, reverse=True)
    selected = tuple(records[:limit])
    with_preview = sum(1 for record in records if "preview.html" not in record.missing)
    with_thumbnail = sum(1 for record in records if "thumbnail.png" not in record.missing)
    missing_required_count = sum(1 for record in records if record.missing)
    return ArtifactInventory(
        repo=repo,
        total=len(records),
        with_preview=with_preview,
        with_thumbnail=with_thumbnail,
        missing_required_count=missing_required_count,
        records=selected,
    )


def _markdown_table(rows: Iterable[tuple[str, ...]], headers: tuple[str, ...]) -> str:
    rendered = ["| " + " | ".join(headers) + " |"]
    rendered.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        rendered.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")
    return "\n".join(rendered)


def _render_inventory(inventory: ArtifactInventory) -> str:
    if not inventory.records:
        return "No artifacts were found under `artifacts/`."

    rows = []
    for record in inventory.records:
        rows.append(
            (
                f"`{record.slug}`",
                record.title,
                record.updated_at,
                record.source_file or "Missing",
                ", ".join(record.missing) if record.missing else "None",
            )
        )
    return _markdown_table(
        rows,
        ("Artifact", "Title", "Last Seen", "Source", "Missing"),
    )


def _render_gate_table(state: WorkflowState) -> str:
    rows = [
        (
            gate.key,
            gate.title,
            gate.owner,
            gate.status,
            gate.evidence,
            gate.note or "",
        )
        for gate in state.gates
    ]
    return _markdown_table(
        rows,
        ("Key", "Gate", "Owner", "Status", "Evidence", "Note"),
    )


def _render_verification_table(state: WorkflowState) -> str:
    if not state.verifications:
        return "No verification records yet."
    rows = [
        (
            record.ran_at,
            f"`{record.command}`",
            record.result,
            record.note,
        )
        for record in state.verifications[-10:]
    ]
    return _markdown_table(rows, ("Ran At", "Command", "Result", "Note"))


def _render_state_markdown(state: WorkflowState, inventory: ArtifactInventory) -> str:
    return f"""# Workflow State

- Target repository: `{state.repo}`
- Workflow name: `{state.workflow_name}`
- Created: {state.created_at}
- Updated: {state.updated_at}
- Linear issue: {state.linear_issue or "Pending"}
- Linear project: {state.linear_project or "Pending"}
- Artifact count: {inventory.total}
- Artifacts with preview: {inventory.with_preview}
- Artifacts with thumbnail: {inventory.with_thumbnail}
- Artifacts missing required files: {inventory.missing_required_count}

## Gate Status

{_render_gate_table(state)}

## Verification Log

{_render_verification_table(state)}

## Operating Rule

Implementation starts only after Codex and Claude have aligned on the best path,
or after the operator explicitly accepts a documented exception.
"""


def _inventory_to_dict(inventory: ArtifactInventory) -> dict:
    return {
        "repo": str(inventory.repo),
        "total": inventory.total,
        "with_preview": inventory.with_preview,
        "with_thumbnail": inventory.with_thumbnail,
        "missing_required_count": inventory.missing_required_count,
        "records": [
            {
                "slug": record.slug,
                "title": record.title,
                "updated_at": record.updated_at,
                "missing": list(record.missing),
                "source_file": record.source_file,
            }
            for record in inventory.records
        ],
    }


def workflow_payload(repo: Path) -> dict:
    repo = repo.expanduser().resolve()
    inventory = inventory_artifact_repository(repo)
    state = load_workflow_state(repo)
    return {
        "repo": str(repo),
        "state_path": str(_state_path(repo)),
        "state": _state_to_dict(state) if state is not None else None,
        "inventory": _inventory_to_dict(inventory),
        "markdown": (
            _render_state_markdown(state, inventory).rstrip()
            if state is not None
            else workflow_status(repo)
        ),
    }


def _workflow_files(
    repo: Path,
    workflow_name: str,
    inventory: ArtifactInventory,
    state: WorkflowState,
    linear_issue: str | None,
    linear_project: str | None,
    claude_gate_note: str | None,
) -> dict[Path, str]:
    generated = _utc_now()
    linear_ref = linear_issue or "Pending"
    linear_project_ref = linear_project or "Pending"
    claude_note = claude_gate_note or (
        "Pending. Run Claude Code in read-only/plan mode before implementation."
    )

    summary = (
        f"- Target repository: `{repo}`\n"
        f"- Workflow name: `{workflow_name}`\n"
        f"- Generated: {generated}\n"
        f"- Linear issue: {linear_ref}\n"
        f"- Linear project: {linear_project_ref}\n"
        f"- Artifact count: {inventory.total}\n"
        f"- Artifacts with preview: {inventory.with_preview}\n"
        f"- Artifacts with thumbnail: {inventory.with_thumbnail}\n"
        f"- Artifacts missing required files: {inventory.missing_required_count}\n"
    )

    return {
        Path("WORKFLOW_STATE.md"): _render_state_markdown(state, inventory),
        Path("ARCHITECT_PACK.md"): f"""# Architect Pack

## Objective

Use `{workflow_name}` as the first repository to test the Codex to Claude
adversarial alignment workflow.

## Repository Snapshot

{summary}

## Artifact Inventory

{_render_inventory(inventory)}

## Source Of Truth Boundary

- Local files in this repository hold evidence, plans, review notes, decisions,
  implementation diffs, and verification logs.
- Linear tracks coordination state, acceptance criteria, blockers, and links.
- Linear should not duplicate generated evidence files or become a second audit
  log.

## First Pilot Question

Can the launcher reliably create the planning, review, reconciliation, and
verification shell before any implementation work starts?
""",
        Path("CODEX_PLAN.md"): """# Codex Plan

## Proposed Path

Pending.

## Acceptance Criteria

- The scope is specific enough for Claude Code to critique.
- The plan names files, commands, expected outputs, and non-goals.
- Risks are explicit before implementation starts.

## Non-Goals

- Pending.
""",
        Path("CLAUDE_CRITIQUE.md"): f"""# Claude Critique

## Gate Status

{claude_note}

## Review Prompt Template

Ask Claude Code to review `ARCHITECT_PACK.md` and `CODEX_PLAN.md` in read-only
or plan mode.

```bash
claude --dangerously-skip-permissions
```

Inside Claude Code, request:

```text
Read-only adversarial review. Do not edit files. Critique CODEX_PLAN.md against
ARCHITECT_PACK.md for architecture risk, missing acceptance criteria, source of
truth drift, and verification gaps. Return required changes before build.
```
""",
        Path("RECONCILIATION.md"): """# Reconciliation

## Claude Objections

Pending.

## Codex Response

Pending.

## Plan Changes

Pending.
""",
        Path("ALIGNMENT_DECISION.md"): """# Alignment Decision

## Decision

Pending.

## Required Before Build

- Codex plan is complete.
- Claude critique has been reviewed.
- Reconciliation notes name accepted and rejected changes.
- Operator exception is documented if Claude review is unavailable.

## Exception Log

None.
""",
        Path("VERIFY.md"): """# Verification

## Commands

Pending.

## Runtime Checks

Pending.

## Artifact Checks

Pending.

## Result

Pending.
""",
        Path("linear/LINEAR_ISSUE_TEMPLATE.md"): f"""# Linear Issue Template

## Title

Workflow Launcher Pilot: {workflow_name}

## Description

Use `{repo}` as the first live repository for the Codex to Claude adversarial
alignment workflow.

## Acceptance Criteria

- `.workflow/WORKFLOW_STATE.md` shows gate status.
- `.workflow/ARCHITECT_PACK.md` captures repository context.
- `.workflow/CODEX_PLAN.md` contains a build plan before code changes.
- `.workflow/CLAUDE_CRITIQUE.md` captures the read-only critique or a documented
  auth/runtime blocker.
- `.workflow/RECONCILIATION.md` records plan changes.
- `.workflow/VERIFY.md` lists executed checks and results.

## Evidence Links

- Local workflow folder: `{repo / WORKFLOW_DIRNAME}`
- Linear project: {linear_project_ref}
- Existing Linear issue: {linear_ref}
""",
    }


def init_workflow(
    repo: Path,
    workflow_name: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    linear_issue: str | None = None,
    linear_project: str | None = None,
    claude_gate_note: str | None = None,
) -> list[WorkflowWrite]:
    repo = repo.expanduser().resolve()
    workflow_name = workflow_name or repo.name
    inventory = inventory_artifact_repository(repo)
    state = _initial_state(
        repo=repo,
        workflow_name=workflow_name,
        linear_issue=linear_issue,
        linear_project=linear_project,
        claude_gate_note=claude_gate_note,
    )
    files = _workflow_files(
        repo=repo,
        workflow_name=workflow_name,
        inventory=inventory,
        state=state,
        linear_issue=linear_issue,
        linear_project=linear_project,
        claude_gate_note=claude_gate_note,
    )
    files[Path(STATE_FILENAME)] = json.dumps(
        _state_to_dict(state),
        indent=2,
        sort_keys=True,
    )
    workflow_dir = repo / WORKFLOW_DIRNAME
    writes: list[WorkflowWrite] = []

    if dry_run:
        for relative_path in files:
            destination = workflow_dir / relative_path
            if destination.exists() and not force:
                writes.append(WorkflowWrite(destination, "exists"))
                continue
            action = "write" if destination.exists() else "create"
            writes.append(WorkflowWrite(destination, action))
        return writes

    with _workflow_state_lock(repo):
        for relative_path, content in files.items():
            destination = workflow_dir / relative_path
            if destination.exists() and not force:
                writes.append(WorkflowWrite(destination, "exists"))
                continue
            action = "write" if destination.exists() else "create"
            writes.append(WorkflowWrite(destination, action))
            _write_text_atomic(destination, content.rstrip() + "\n")

    return writes


def inspect_workflow(repo: Path) -> str:
    inventory = inventory_artifact_repository(repo)
    summary = [
        f"Repository: {inventory.repo}",
        f"Artifacts: {inventory.total}",
        f"With preview: {inventory.with_preview}",
        f"With thumbnail: {inventory.with_thumbnail}",
        f"Missing required files: {inventory.missing_required_count}",
        "",
        _render_inventory(inventory),
    ]
    return "\n".join(summary)


def workflow_status(repo: Path) -> str:
    repo = repo.expanduser().resolve()
    inventory = inventory_artifact_repository(repo)
    state = load_workflow_state(repo)
    if state is None:
        return "\n".join(
            [
                inspect_workflow(repo),
                "",
                f"No workflow state found at `{_state_path(repo)}`.",
                "Run `hermes workflow init` before advancing gates.",
            ]
        )
    return _render_state_markdown(state, inventory).rstrip()


def _replace_gate(
    state: WorkflowState,
    gate_key: str,
    status: str,
    evidence: str | None,
    note: str | None,
) -> WorkflowState:
    if status not in GATE_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}. Expected one of: {', '.join(sorted(GATE_STATUSES))}"
        )
    updated = _utc_now()
    found = False
    gates = []
    for gate in state.gates:
        if gate.key != gate_key:
            gates.append(gate)
            continue
        found = True
        gates.append(
            replace(
                gate,
                status=status,
                evidence=gate.evidence if evidence is None else evidence,
                note=gate.note if note is None else note,
                updated_at=updated,
            )
        )
    if not found:
        valid = ", ".join(gate.key for gate in state.gates)
        raise ValueError(f"Unknown gate {gate_key!r}. Expected one of: {valid}")
    return replace(state, gates=tuple(gates), updated_at=updated)


def _refresh_workflow_state_markdown(repo: Path, state: WorkflowState) -> None:
    inventory = inventory_artifact_repository(repo)
    destination = repo / WORKFLOW_DIRNAME / "WORKFLOW_STATE.md"
    _write_text_atomic(
        destination,
        _render_state_markdown(state, inventory).rstrip() + "\n",
    )


def advance_workflow_gate(
    repo: Path,
    gate_key: str,
    status: str,
    evidence: str | None = None,
    note: str | None = None,
) -> WorkflowState:
    repo = repo.expanduser().resolve()
    with _workflow_state_lock(repo):
        state = load_workflow_state(repo)
        if state is None:
            raise FileNotFoundError(f"No workflow state found at {_state_path(repo)}")
        state = _replace_gate(state, gate_key, status, evidence, note)
        _write_workflow_state(repo, state)
        _refresh_workflow_state_markdown(repo, state)
        return state


def record_verification(
    repo: Path,
    command: str,
    result: str,
    note: str | None = None,
) -> WorkflowState:
    if result not in VERIFY_RESULTS:
        raise ValueError(
            f"Invalid result {result!r}. Expected one of: {', '.join(sorted(VERIFY_RESULTS))}"
        )
    repo = repo.expanduser().resolve()
    with _workflow_state_lock(repo):
        state = load_workflow_state(repo)
        if state is None:
            raise FileNotFoundError(f"No workflow state found at {_state_path(repo)}")

        now = _utc_now()
        record = VerificationRecord(
            command=command,
            result=result,
            note=note or "",
            ran_at=now,
        )
        state = replace(
            state,
            verifications=state.verifications + (record,),
            updated_at=now,
        )
        if result == "passed":
            state = _replace_gate(
                state,
                "verification",
                "done",
                "VERIFY.md",
                note or f"Latest check passed: {command}",
            )
        else:
            state = _replace_gate(
                state,
                "verification",
                "blocked",
                "VERIFY.md",
                note or f"Latest check {result}: {command}",
            )
        _write_workflow_state(repo, state)
        _refresh_workflow_state_markdown(repo, state)
        return state


def _print_writes(writes: Iterable[WorkflowWrite], dry_run: bool) -> None:
    prefix = "would " if dry_run else ""
    for write in writes:
        if write.action == "exists":
            print(f"exists  {write.path}")
        else:
            print(f"{prefix}{write.action:<6} {write.path}")


def workflow_command(args: argparse.Namespace) -> None:
    repo = Path(args.repo) if args.repo else default_artifact_repository()
    action = getattr(args, "workflow_action", None)
    if action == "inspect":
        print(inspect_workflow(repo))
        return
    if action == "status":
        print(workflow_status(repo))
        return
    if action == "init":
        writes = init_workflow(
            repo=repo,
            workflow_name=args.name,
            dry_run=args.dry_run,
            force=args.force,
            linear_issue=args.linear_issue,
            linear_project=args.linear_project,
            claude_gate_note=args.claude_gate_note,
        )
        _print_writes(writes, args.dry_run)
        return
    if action == "advance":
        try:
            state = advance_workflow_gate(
                repo=repo,
                gate_key=args.gate,
                status=args.status,
                evidence=args.evidence,
                note=args.note,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        print(f"{args.gate}: {args.status}")
        print(f"state: {_state_path(Path(state.repo))}")
        return
    if action == "verify":
        try:
            state = record_verification(
                repo=repo,
                command=args.command,
                result=args.result,
                note=args.note,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        print(f"verification: {args.result}")
        print(f"state: {_state_path(Path(state.repo))}")
        return
    raise SystemExit("Missing workflow action. Use `hermes workflow --help`.")


def register_workflow_subparser(subparsers) -> None:
    workflow_parser = subparsers.add_parser(
        "workflow",
        help="Create and inspect Codex to Claude workflow gates",
        description=(
            "Create a local .workflow shell for Codex planning, Claude Code "
            "adversarial review, reconciliation, verification, and Linear-ready "
            "coordination."
        ),
    )
    workflow_sub = workflow_parser.add_subparsers(dest="workflow_action")

    inspect_parser = workflow_sub.add_parser(
        "inspect",
        help="Inspect a repository before creating workflow files",
    )
    inspect_parser.add_argument(
        "--repo",
        default=None,
        help="Repository path. Defaults to Hermes artifact repository.",
    )

    init_parser = workflow_sub.add_parser(
        "init",
        help="Create workflow gate files in the target repository",
    )
    init_parser.add_argument(
        "--repo",
        default=None,
        help="Repository path. Defaults to Hermes artifact repository.",
    )
    init_parser.add_argument(
        "--name",
        default=None,
        help="Human-readable workflow name. Defaults to the repository name.",
    )
    init_parser.add_argument(
        "--linear-issue",
        default=None,
        help="Existing Linear issue URL or identifier to include in the brief.",
    )
    init_parser.add_argument(
        "--linear-project",
        default=None,
        help="Linear project name or URL to include in the brief.",
    )
    init_parser.add_argument(
        "--claude-gate-note",
        default=None,
        help="Current Claude gate status or blocker note.",
    )
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned writes without creating files.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing workflow files.",
    )

    status_parser = workflow_sub.add_parser(
        "status",
        help="Print workflow gate status from .workflow/state.json",
    )
    status_parser.add_argument(
        "--repo",
        default=None,
        help="Repository path. Defaults to Hermes artifact repository.",
    )

    advance_parser = workflow_sub.add_parser(
        "advance",
        help="Update a workflow gate status",
    )
    advance_parser.add_argument(
        "--repo",
        default=None,
        help="Repository path. Defaults to Hermes artifact repository.",
    )
    advance_parser.add_argument(
        "--gate",
        required=True,
        help="Gate key, for example codex_plan, claude_review, or verification.",
    )
    advance_parser.add_argument(
        "--status",
        required=True,
        choices=sorted(GATE_STATUSES),
        help="New gate status.",
    )
    advance_parser.add_argument(
        "--evidence",
        default=None,
        help="Evidence path or reference for this gate.",
    )
    advance_parser.add_argument(
        "--note",
        default=None,
        help="Short note explaining the gate update.",
    )

    verify_parser = workflow_sub.add_parser(
        "verify",
        help="Record a verification result and update the verification gate",
    )
    verify_parser.add_argument(
        "--repo",
        default=None,
        help="Repository path. Defaults to Hermes artifact repository.",
    )
    verify_parser.add_argument(
        "--command",
        required=True,
        help="Verification command or runtime check that was executed.",
    )
    verify_parser.add_argument(
        "--result",
        required=True,
        choices=sorted(VERIFY_RESULTS),
        help="Verification result.",
    )
    verify_parser.add_argument(
        "--note",
        default=None,
        help="Short note or blocker details.",
    )
    workflow_parser.set_defaults(func=workflow_command)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Hermes workflow launcher")
    subparsers = parser.add_subparsers(dest="command")
    register_workflow_subparser(subparsers)
    parsed = parser.parse_args(argv)
    if not hasattr(parsed, "func"):
        parser.print_help()
        return
    parsed.func(parsed)


if __name__ == "__main__":
    main()
