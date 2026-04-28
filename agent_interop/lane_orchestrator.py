"""Offline lane orchestration primitives for Hermes/OpenClaw/Codex workflows.

The module is deliberately conservative: it does not invoke Codex, OpenClaw,
NotebookLM, browsers, OpenCLI, or messaging adapters.  It creates typed task
intent envelopes, chooses the lane that should own the next step, and writes
local handoff/observability artifacts that can be smoke-tested before any live
adapter is connected.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class Lane(str, Enum):
    """Supported high-level execution lanes.

    Values intentionally describe roles instead of concrete commands.  The live
    implementation can map these lanes to Codex CLI, NotebookLM, Hermes browser,
    OpenCLI, or OpenClaw skills only after policy gates approve it.
    """

    NOTEBOOKLM_COMPRESSION = "notebooklm_compression"
    CODEX_IMPLEMENTATION = "codex_implementation"
    HERMES_BROWSER = "hermes_browser"
    OPENCLI_EXTERNAL_SEARCH = "opencli_external_search"
    OPENCLAW_SEARCH_SKILL = "openclaw_search_skill"
    HERMES_SYNTHESIS = "hermes_synthesis"


@dataclass(frozen=True)
class TaskEnvelope:
    """Portable, side-effect-free task envelope passed between agents."""

    task_id: str
    source: str
    request: str
    lane: Lane | None = None
    input_artifacts: list[Path] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OfflineTaskResult:
    """Result of an offline lane run."""

    task_id: str
    lane: Lane
    status: str
    output_dir: Path
    manifest_path: Path
    report_path: Path
    output_artifacts: list[Path]


_LANE_AGENTS: dict[Lane, list[str]] = {
    Lane.NOTEBOOKLM_COMPRESSION: ["openclaw", "notebooklm", "hermes"],
    Lane.CODEX_IMPLEMENTATION: ["openclaw", "codex", "hermes"],
    Lane.HERMES_BROWSER: ["openclaw", "hermes-browser", "hermes"],
    Lane.OPENCLI_EXTERNAL_SEARCH: ["openclaw", "opencli", "hermes"],
    Lane.OPENCLAW_SEARCH_SKILL: ["openclaw", "openclaw-search-skill", "hermes"],
    Lane.HERMES_SYNTHESIS: ["openclaw", "hermes"],
}

_CODING_RE = re.compile(r"\b(code|coding|repo|implement|refactor|pytest|test|e2e|smoke|fix|bug)\b", re.I)
_RESEARCH_RE = re.compile(r"\b(research|sources?|notebooklm|summary|summari[sz]e|brief|report|整理|彙整)\b", re.I)
_BROWSER_RE = re.compile(r"\b(browser|web page|playwright|screenshot|crawl|瀏覽器)\b", re.I)
_EXTERNAL_RE = re.compile(r"\b(youtube|x/twitter|twitter|reddit|github|huggingface|threads|facebook|douyin|tiktok|小紅書|抖音|微信|opencli)\b", re.I)
_OPENCLAW_RE = re.compile(r"\b(openclaw|clawd|rex|blake|search skill|搜索技能)\b", re.I)

_LANE_LABELS: dict[Lane, str] = {
    Lane.NOTEBOOKLM_COMPRESSION: "NotebookLM compression lane",
    Lane.CODEX_IMPLEMENTATION: "Codex CLI implementation lane",
    Lane.HERMES_BROWSER: "Hermes browser lane",
    Lane.OPENCLI_EXTERNAL_SEARCH: "OpenCLI external search lane",
    Lane.OPENCLAW_SEARCH_SKILL: "OpenClaw search skill lane",
    Lane.HERMES_SYNTHESIS: "Hermes synthesis lane",
}


def _lane_label(lane: Lane) -> str:
    return _LANE_LABELS[lane]


def _safe_segment(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return safe[:96] or "task"


def build_task_envelope(
    *,
    request: str,
    source: str,
    task_id: str | None = None,
    lane: Lane | str | None = None,
    input_artifacts: Iterable[str | Path] | None = None,
    metadata: dict[str, Any] | None = None,
) -> TaskEnvelope:
    """Build and validate a local interop task envelope."""

    normalized_request = request.strip()
    if not normalized_request:
        raise ValueError("request must not be empty")
    normalized_source = source.strip()
    if not normalized_source:
        raise ValueError("source must not be empty")
    resolved_lane = Lane(lane) if lane else None
    resolved_id = task_id or f"task-{int(time.time())}-{_safe_segment(normalized_request)[:32]}"
    return TaskEnvelope(
        task_id=_safe_segment(resolved_id),
        source=normalized_source,
        request=normalized_request,
        lane=resolved_lane,
        input_artifacts=[Path(item).expanduser() for item in input_artifacts or []],
        metadata=dict(metadata or {}),
    )


def route_task(envelope: TaskEnvelope) -> Lane:
    """Choose the next owner lane with deterministic, inspectable rules."""

    if envelope.lane is not None:
        return envelope.lane
    text = envelope.request
    if _CODING_RE.search(text):
        return Lane.CODEX_IMPLEMENTATION
    if envelope.input_artifacts and _RESEARCH_RE.search(text):
        return Lane.NOTEBOOKLM_COMPRESSION
    if _BROWSER_RE.search(text):
        return Lane.HERMES_BROWSER
    if _EXTERNAL_RE.search(text):
        return Lane.OPENCLI_EXTERNAL_SEARCH
    if _OPENCLAW_RE.search(text):
        return Lane.OPENCLAW_SEARCH_SKILL
    if _RESEARCH_RE.search(text):
        return Lane.NOTEBOOKLM_COMPRESSION
    return Lane.HERMES_SYNTHESIS


def _read_input_artifacts(paths: list[Path]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            sources.append({"path": str(path), "exists": False, "chars": 0, "preview": ""})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        sources.append({"path": str(path), "exists": True, "chars": len(text), "preview": text[:1200]})
    return sources


def _write_notebooklm_brief(envelope: TaskEnvelope, output_dir: Path) -> Path:
    sources = _read_input_artifacts(envelope.input_artifacts)
    lines = [
        "# NotebookLM compression lane — offline brief",
        "",
        f"Task: `{envelope.task_id}`",
        "",
        "## Request",
        "",
        envelope.request,
        "",
        "## Source pack",
        "",
    ]
    if not sources:
        lines.append("- No local sources supplied. Live lane should ingest source URLs/files before synthesis.")
    for idx, source in enumerate(sources, start=1):
        status = "found" if source["exists"] else "missing"
        lines.extend([
            f"### Source {idx}: `{source['path']}` ({status}, {source['chars']} chars)",
            "",
            source["preview"] or "(empty)",
            "",
        ])
    lines.extend(
        [
            "## Implementation recommendation",
            "",
            "- Keep OpenClaw as control plane: intake, routing, governance, task/session state.",
            "- Use Codex CLI only inside scoped repo/worktree implementation lanes.",
            "- Use NotebookLM as research compression, not as the long-running orchestrator.",
            "- Use Hermes for browser/tool execution, long-running background jobs, reports, and skill sedimentation.",
            "- Use OpenCLI/OpenClaw search skills as replaceable external-data adapters.",
            "",
            "## Safety note",
            "",
            "This smoke run is offline and writes only local artifacts. No external messages sent.",
        ]
    )
    path = output_dir / "implementation_brief.md"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _write_codex_handoff(envelope: TaskEnvelope, output_dir: Path) -> Path:
    path = output_dir / "codex_handoff.md"
    path.write_text(
        "\n".join(
            [
                "# Codex CLI implementation lane — offline handoff",
                "",
                f"Task: `{envelope.task_id}`",
                "",
                "## Scope",
                envelope.request,
                "",
                "## Required execution shape",
                "",
                "1. Create or select an isolated worktree before code changes.",
                "2. Keep Codex CLI focused on repo-local implementation and refactor work only.",
                "3. Return patches plus verification commands, not broad agent orchestration decisions.",
                "4. Let Hermes/OpenClaw own observability, artifact capture, and closeout.",
                "",
                "## verification commands",
                "",
                "```bash",
                "pytest -q <targeted-tests>",
                "python scripts/<smoke-script>.py --dry-run",
                "```",
                "",
                "Safety: this offline handoff did not run Codex or modify a repository.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_generic_handoff(envelope: TaskEnvelope, lane: Lane, output_dir: Path) -> Path:
    path = output_dir / f"{lane.value}_handoff.md"
    path.write_text(
        f"# {lane.value} offline handoff\n\nTask: `{envelope.task_id}`\n\n{envelope.request}\n\nNo external messages sent.\n",
        encoding="utf-8",
    )
    return path


def _artifact_entry(path: Path, key: str) -> dict[str, str]:
    return {key: str(path)}


def run_offline_task(envelope: TaskEnvelope, *, output_dir: str | Path) -> OfflineTaskResult:
    """Run one lane in offline smoke mode and write observability artifacts."""

    lane = route_task(envelope)
    out = Path(output_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    if lane is Lane.NOTEBOOKLM_COMPRESSION:
        artifact = _write_notebooklm_brief(envelope, out)
        artifacts = [_artifact_entry(artifact, "implementation_brief")]
    elif lane is Lane.CODEX_IMPLEMENTATION:
        artifact = _write_codex_handoff(envelope, out)
        artifacts = [_artifact_entry(artifact, "codex_handoff")]
    else:
        artifact = _write_generic_handoff(envelope, lane, out)
        artifacts = [_artifact_entry(artifact, f"{lane.value}_handoff")]

    manifest = {
        "task_id": envelope.task_id,
        "source": envelope.source,
        "lane": lane.value,
        "status": "completed",
        "risk": "low-offline-dry-run",
        "agents": _LANE_AGENTS[lane],
        "request": envelope.request,
        "metadata": envelope.metadata,
        "input_artifacts": [str(path) for path in envelope.input_artifacts],
        "output_artifacts": artifacts,
        "external_side_effects": [],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    manifest_path = out / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report_path = out / "task_observability_report.md"
    report_path.write_text(
        "\n".join(
            [
                "# Agent lane task observability report",
                "",
                f"- Task ID: `{envelope.task_id}`",
                f"- Source: `{envelope.source}`",
                f"- Lane: `{lane.value}`",
                f"- Lane label: {_lane_label(lane)}",
                f"- Agents: {', '.join(_LANE_AGENTS[lane])}",
                "- Status: completed",
                "- Risk: low-offline-dry-run",
                "- Side effects: No external messages sent; local artifact writes only.",
                "",
                "## Artifacts",
                "",
                *[f"- `{next(iter(item.values()))}`" for item in artifacts],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return OfflineTaskResult(
        task_id=envelope.task_id,
        lane=lane,
        status="completed",
        output_dir=out,
        manifest_path=manifest_path,
        report_path=report_path,
        output_artifacts=[artifact],
    )


def run_smoke(output_dir: str | Path, *, source_path: str | Path | None = None) -> OfflineTaskResult:
    """Convenience smoke entrypoint used by scripts and future CI."""

    artifacts = [Path(source_path).expanduser()] if source_path else []
    envelope = build_task_envelope(
        task_id="hermes-openclaw-codex-smoke",
        source="local-smoke",
        request="Research OpenClaw Hermes Codex workflow and produce implementation brief",
        input_artifacts=artifacts,
    )
    return run_offline_task(envelope, output_dir=output_dir)
