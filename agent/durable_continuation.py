"""Durable continuation packet rendering and writer helpers.

These helpers persist the minimum run-state needed for another Hermes session to
continue a long job without rediscovering completed work. They intentionally use
plain Markdown files so projects can review and edit the handoff in normal docs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable, Sequence


@dataclass(frozen=True)
class DurableContinuationPacket:
    """Structured state for a resumable Hermes work cycle."""

    job_name: str
    current_phase: str
    exact_next_action: str
    completed_tasks: Sequence[str] = field(default_factory=tuple)
    pending_tasks: Sequence[str] = field(default_factory=tuple)
    blockers: Sequence[str] = field(default_factory=tuple)
    changed_files: Sequence[str] = field(default_factory=tuple)
    evidence_links: Sequence[str] = field(default_factory=tuple)
    verification_completed: Sequence[str] = field(default_factory=tuple)
    remaining_verification: Sequence[str] = field(default_factory=tuple)
    do_not_repeat: Sequence[str] = field(default_factory=tuple)
    last_updated: str | None = None


@dataclass(frozen=True)
class DurableContinuationWriteResult:
    """Paths written by :func:`write_durable_continuation`."""

    job_ledger_path: Path
    next_run_path: Path


def render_job_ledger(packet: DurableContinuationPacket) -> str:
    """Render ``docs/Job Ledger.md`` from a continuation packet."""
    updated = _last_updated(packet)
    sections = [
        "# Job Ledger",
        "## Current job",
        f"Job name: {_required_text(packet.job_name, 'job_name')}",
        f"Current phase: `{_required_text(packet.current_phase, 'current_phase')}`",
        f"Last updated: {updated}",
        "## Completed tasks",
        _bullet_list(packet.completed_tasks),
        "## Pending tasks",
        _numbered_list(packet.pending_tasks),
        "## Blockers",
        _bullet_list(packet.blockers),
        "## Changed files",
        _bullet_list(packet.changed_files),
        "## Evidence links",
        _bullet_list(packet.evidence_links),
        "## Verification completed",
        _bullet_list(packet.verification_completed),
        "## Remaining verification",
        _bullet_list(packet.remaining_verification),
        "## Exact next action",
        _required_text(packet.exact_next_action, "exact_next_action"),
        "## Work that must not be repeated",
        _bullet_list(packet.do_not_repeat),
    ]
    return "\n\n".join(sections) + "\n"


def render_next_run(packet: DurableContinuationPacket) -> str:
    """Render ``docs/NEXT_RUN.md`` from a continuation packet."""
    updated = _last_updated(packet)
    sections = [
        "# NEXT_RUN",
        "## Status",
        f"Status: `{_required_text(packet.current_phase, 'current_phase')}`",
        f"Last updated: {updated}",
        "## Completed",
        _bullet_list(packet.completed_tasks),
        "## Remaining work",
        _bullet_list(packet.pending_tasks),
        "## Verification completed",
        _bullet_list(packet.verification_completed),
        "## Verification still needed",
        _bullet_list(packet.remaining_verification),
        "## Next action",
        _required_text(packet.exact_next_action, "exact_next_action"),
        "## Do not repeat",
        _bullet_list(packet.do_not_repeat),
    ]
    return "\n\n".join(sections) + "\n"


def write_durable_continuation(
    project_root: str | Path,
    packet: DurableContinuationPacket,
    *,
    docs_dir: str | Path = "docs",
) -> DurableContinuationWriteResult:
    """Write durable continuation Markdown files under ``project_root``.

    The docs directory must resolve inside ``project_root``. Each file is written
    through a temporary sibling and atomically replaced to avoid partial handoffs
    if the process is interrupted mid-write.
    """
    root = Path(project_root).expanduser().resolve()
    docs_path = _resolve_docs_dir(root, docs_dir)
    docs_path.mkdir(parents=True, exist_ok=True)

    job_ledger_path = docs_path / "Job Ledger.md"
    next_run_path = docs_path / "NEXT_RUN.md"

    _atomic_write_text(job_ledger_path, render_job_ledger(packet))
    _atomic_write_text(next_run_path, render_next_run(packet))

    return DurableContinuationWriteResult(
        job_ledger_path=job_ledger_path,
        next_run_path=next_run_path,
    )


def _last_updated(packet: DurableContinuationPacket) -> str:
    if packet.last_updated:
        return packet.last_updated
    return date.today().isoformat()


def _required_text(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _clean_items(items: Iterable[str]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()]


def _bullet_list(items: Iterable[str]) -> str:
    cleaned = _clean_items(items)
    if not cleaned:
        return "- None recorded."
    return "\n".join(f"- {item}" for item in cleaned)


def _numbered_list(items: Iterable[str]) -> str:
    cleaned = _clean_items(items)
    if not cleaned:
        return "- None recorded."
    return "\n".join(f"{index}. {item}" for index, item in enumerate(cleaned, start=1))


def _resolve_docs_dir(root: Path, docs_dir: str | Path) -> Path:
    raw_docs = Path(docs_dir).expanduser()
    docs_path = raw_docs if raw_docs.is_absolute() else root / raw_docs
    resolved = docs_path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("docs_dir must stay inside project_root") from exc
    return resolved


def _atomic_write_text(path: Path, content: str) -> None:
    temp_path: Path | None = None
    replaced = False
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
        replaced = True
        _fsync_directory(path.parent)
    finally:
        if temp_path is not None and not replaced and temp_path.exists():
            temp_path.unlink()


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
