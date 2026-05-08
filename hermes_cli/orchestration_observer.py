"""Observe Hermes phase events and mirror them into durable Kanban state.

The architecture says Codex phase execution hands events/logs back to Hermes.
This module is the narrow bridge used by the guarded phase wrapper: it turns
repo-local ``.hermes/events`` JSON files into Kanban comments and terminal task
state so the dashboard/gateway notifier can see what happened even if the
interactive agent is busy or gone.
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from hermes_cli import kanban_db as kb


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return data


def _event_summary(event: dict[str, Any]) -> str:
    summary = str(event.get("summary") or "").strip()
    if summary:
        return summary
    question = str(event.get("question") or "").strip()
    if question:
        return question
    tail = str(event.get("tail") or "").strip()
    if tail:
        return tail.splitlines()[-1][:400]
    return str(event.get("type") or "phase event")


def _find_terminal_event(event_dir: Path, phase_id: str) -> Optional[Path]:
    preferred = [
        event_dir / f"{phase_id}-complete.json",
        event_dir / f"{phase_id}-needs-input.json",
    ]
    for path in preferred:
        if path.exists():
            return path

    process_events = sorted(event_dir.glob(f"*-{phase_id}-process-*.json"))
    if process_events:
        return process_events[-1]
    return None


def _has_incomplete_later_phase(repo: Path, phase_id: str) -> bool:
    phase_dir = repo / ".hermes" / "phases"
    event_dir = repo / ".hermes" / "events"
    if not phase_dir.is_dir():
        return False

    seen_current = False
    for phase in sorted(phase_dir.glob("*.md")):
        candidate = phase.stem
        if candidate == phase_id:
            seen_current = True
            continue
        if not seen_current:
            continue
        if not (event_dir / f"{candidate}-complete.json").exists():
            return True
    return False


def _git_value(repo: Path, args: list[str]) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except Exception:
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _phase_order(repo: Path) -> list[str]:
    phase_dir = repo / ".hermes" / "phases"
    if not phase_dir.is_dir():
        return []
    return [p.stem for p in sorted(phase_dir.glob("*.md"))]


def _write_flow_graph(
    *,
    task_id: str,
    repo: Path,
    phase_id: str,
    event_type: str,
    summary: str,
    metadata: dict[str, Any],
) -> Optional[Path]:
    """Write an SVG artifact that explains where the change enters the project."""
    artifact_dir = Path("/home/ubuntu/.hermes/kanban/artifacts")
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    branch = metadata.get("branch") or _git_value(repo, ["branch", "--show-current"])
    remote = metadata.get("remote_url") or _git_value(repo, ["remote", "get-url", "origin"])
    changed = metadata.get("changed_files") if isinstance(metadata.get("changed_files"), list) else []

    def esc(value: Any) -> str:
        return html.escape(str(value or ""), quote=True)

    def file_exists(rel: str) -> bool:
        return (repo / rel).exists()

    def classify_file(rel: str) -> tuple[str, str]:
        name = Path(rel).name
        if "await-pre-planning-approval" in name:
            return ("Pre-planning gate", "New executable guard before Planner")
        if name == "pending-input.json":
            return ("Pending input state", "Blocked request envelope")
        if name.startswith("approval-pre-planning"):
            return ("Developer approval", "Approval artifact")
        if rel.startswith(".hermes/events/"):
            return ("Phase event", "Codex/Hermes handoff event")
        if rel.startswith(".hermes/phases/"):
            return ("Phase plan", "Bounded implementation phase")
        return ("Changed file", rel)

    change_nodes = []
    for rel in changed[:6]:
        label, detail = classify_file(str(rel))
        change_nodes.append((str(rel), label, detail))
    if not change_nodes:
        change_nodes.append(("(none reported)", "Changed file", "No changed_files reported"))

    has_approval = file_exists(".hermes/approval-pre-planning.json")
    approval_label = "approved" if has_approval else "missing -> block"

    changed_lines = []
    for file_name in changed[:8]:
        changed_lines.append(str(file_name))
    if not changed_lines:
        changed_lines = ["(no changed_files reported)"]

    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="820" viewBox="0 0 1280 820">',
        "<defs><style>",
        ".bg{fill:#0f172a}.band{fill:#111827;stroke:#334155;stroke-width:2}.source{fill:#172554;stroke:#60a5fa;stroke-width:2}.gate{fill:#78350f;stroke:#f59e0b;stroke-width:2}.state{fill:#064e3b;stroke:#10b981;stroke-width:2}.next{fill:#312e81;stroke:#818cf8;stroke-width:2}.file{fill:#1f2937;stroke:#64748b;stroke-width:2}",
        ".title{fill:#f8fafc;font:700 28px ui-sans-serif,system-ui}.text{fill:#e5e7eb;font:18px ui-sans-serif,system-ui}.small{fill:#cbd5e1;font:14px ui-sans-serif,system-ui}.mono{fill:#cbd5e1;font:14px ui-monospace,SFMono-Regular,Menlo,monospace}.arrow{stroke:#94a3b8;stroke-width:3;marker-end:url(#arrow);fill:none}.dash{stroke:#64748b;stroke-width:2;stroke-dasharray:7 7;fill:none}",
        "</style><marker id=\"arrow\" markerWidth=\"12\" markerHeight=\"8\" refX=\"10\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L12,4 L0,8 Z\" fill=\"#94a3b8\"/></marker></defs>",
        '<rect class="bg" x="0" y="0" width="1280" height="820"/>',
        f'<text class="title" x="48" y="56">Project Change Flow - {esc(task_id)}</text>',
        f'<text class="small" x="48" y="86">Repo: {esc(repo)} | Branch: {esc(branch)} | Remote: {esc(remote or "(none)")}</text>',
        f'<text class="small" x="48" y="112">Feature slice: {esc(phase_id)} - pre-planning review pause</text>',
    ]

    svg.extend([
        '<rect class="source" x="60" y="170" width="220" height="112" rx="14"/>',
        '<text class="text" x="82" y="210">User request</text>',
        '<text class="small" x="82" y="240">Design URL / screenshot / brief</text>',
        '<text class="small" x="82" y="264">enters Hermes intake</text>',

        '<rect class="gate" x="360" y="170" width="260" height="112" rx="14"/>',
        '<text class="text" x="382" y="210">Pre-planning gate</text>',
        '<text class="small" x="382" y="240">await-pre-planning-approval.ts</text>',
        '<text class="small" x="382" y="264">runs before Planner starts</text>',

        '<rect class="state" x="700" y="170" width="250" height="112" rx="14"/>',
        '<text class="text" x="722" y="210">Pending input state</text>',
        '<text class="small" x="722" y="240">.hermes/pending-input.json</text>',
        '<text class="small" x="722" y="264">status=blocked, phase=pre-planning</text>',

        '<rect class="next" x="1030" y="170" width="190" height="112" rx="14"/>',
        '<text class="text" x="1052" y="210">Planner</text>',
        f'<text class="small" x="1052" y="240">approval: {esc(approval_label)}</text>',
        '<text class="small" x="1052" y="264">only proceeds if approved</text>',

        '<path class="arrow" d="M280 226 H350"/>',
        '<path class="arrow" d="M620 226 H690"/>',
        '<path class="arrow" d="M950 226 H1020"/>',
        '<path class="dash" d="M1125 282 V330"/>',
        '<text class="small" x="1012" y="326">without approval, workflow stops here</text>',

        '<rect class="band" x="60" y="360" width="1160" height="156" rx="14"/>',
        '<text class="text" x="82" y="400">What changed in the project</text>',
        f'<text class="small" x="82" y="430">Summary: {esc(summary[:250])}</text>',
    ])

    x_positions = [82, 432, 782]
    y_positions = [456, 456, 456, 560, 560, 560]
    for idx, (rel, label, detail) in enumerate(change_nodes[:6]):
        x = x_positions[idx % 3]
        y = y_positions[idx]
        svg.append(f'<rect class="file" x="{x}" y="{y}" width="310" height="72" rx="10"/>')
        svg.append(f'<text class="small" x="{x + 14}" y="{y + 28}">{esc(label)}</text>')
        svg.append(f'<text class="mono" x="{x + 14}" y="{y + 52}">{esc(rel[:38])}</text>')

    svg.extend([
        '<rect class="band" x="60" y="640" width="1160" height="104" rx="14"/>',
        '<text class="text" x="82" y="678">Runtime decision</text>',
        '<text class="small" x="82" y="708">If .hermes/approval-pre-planning.json has approved=true, the script exits 0 and Planner may continue.</text>',
        '<text class="small" x="82" y="732">If approval is missing, it preserves request metadata, writes blocked pending input, exits non-zero, and prevents looped execution.</text>',
    ])
    svg.append("</svg>")

    path = artifact_dir / f"{task_id}-{phase_id}-flow.svg"
    try:
        path.write_text("\n".join(svg), encoding="utf-8")
    except OSError:
        return None
    return path


def record_phase_started(
    *,
    task_id: str,
    repo: Path,
    phase_id: str,
    branch: str,
    log_path: Path,
    author: str = "hermes-codex-phase",
) -> None:
    """Append a Kanban comment that a bounded Codex phase started."""
    kb.init_db()
    with kb.connect() as conn:
        kb.add_comment(
            conn,
            task_id,
            author,
            (
                f"PHASE STARTED: {phase_id}\n"
                f"repo: {repo}\n"
                f"branch: {branch}\n"
                f"log: {log_path}"
            ),
        )


def record_phase_finished(
    *,
    task_id: str,
    repo: Path,
    phase_id: str,
    event_dir: Path,
    log_path: Path,
    exit_code: int,
    author: str = "hermes-codex-phase",
) -> str:
    """Mirror the final phase event into Kanban and return the action taken."""
    kb.init_db()
    event_path = _find_terminal_event(event_dir, phase_id)
    event: dict[str, Any] = {}
    if event_path is not None:
        event = _load_json(event_path)

    event_type = str(event.get("type") or "")
    summary = _event_summary(event) if event else f"phase exited with code {exit_code}"
    metadata = {
        "repo": str(repo),
        "phase": phase_id,
        "event_path": str(event_path) if event_path else None,
        "log_path": str(log_path),
        "exit_code": exit_code,
        "event_type": event_type or None,
        "branch": _git_value(repo, ["branch", "--show-current"]),
        "remote_url": _git_value(repo, ["remote", "get-url", "origin"]),
    }
    if isinstance(event.get("changed_files"), list):
        metadata["changed_files"] = event["changed_files"]
    if isinstance(event.get("commands_run"), list):
        metadata["commands_run"] = event["commands_run"]
    if isinstance(event.get("tests"), dict):
        metadata["tests"] = event["tests"]

    flow_graph = _write_flow_graph(
        task_id=task_id,
        repo=repo,
        phase_id=phase_id,
        event_type=event_type,
        summary=summary,
        metadata=metadata,
    )
    if flow_graph is not None:
        metadata["flow_graph"] = str(flow_graph)
        metadata["artifacts"] = [str(flow_graph)]

    with kb.connect() as conn:
        kb.add_comment(
            conn,
            task_id,
            author,
            (
                f"PHASE FINISHED: {phase_id}\n"
                f"type: {event_type or 'missing_event'}\n"
                f"exit_code: {exit_code}\n"
                f"event: {event_path or '(none)'}\n"
                f"log: {log_path}\n"
                f"summary: {summary}"
            ),
        )

        if event_type == "phase_complete" and exit_code == 0:
            if _has_incomplete_later_phase(repo, phase_id):
                reason = f"phase complete, review before next phase: {summary}"
                kb.block_task(conn, task_id, reason=reason, metadata=metadata)
                return "blocked"
            kb.complete_task(
                conn,
                task_id,
                result=summary,
                summary=summary,
                metadata=metadata,
            )
            return "completed"

        reason = summary
        if event_type == "needs_input":
            reason = f"needs input: {summary}"
        elif exit_code != 0:
            reason = f"phase failed: {summary}"
        kb.block_task(conn, task_id, reason=reason, metadata=metadata)
        return "blocked"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-orchestration-observer")
    sub = parser.add_subparsers(dest="command", required=True)

    started = sub.add_parser("phase-started")
    started.add_argument("--task-id", required=True)
    started.add_argument("--repo", required=True)
    started.add_argument("--phase", required=True)
    started.add_argument("--branch", required=True)
    started.add_argument("--log-path", required=True)

    finished = sub.add_parser("phase-finished")
    finished.add_argument("--task-id", required=True)
    finished.add_argument("--repo", required=True)
    finished.add_argument("--phase", required=True)
    finished.add_argument("--event-dir", required=True)
    finished.add_argument("--log-path", required=True)
    finished.add_argument("--exit-code", required=True, type=int)

    args = parser.parse_args(argv)
    if args.command == "phase-started":
        record_phase_started(
            task_id=args.task_id,
            repo=Path(args.repo),
            phase_id=args.phase,
            branch=args.branch,
            log_path=Path(args.log_path),
        )
    else:
        action = record_phase_finished(
            task_id=args.task_id,
            repo=Path(args.repo),
            phase_id=args.phase,
            event_dir=Path(args.event_dir),
            log_path=Path(args.log_path),
            exit_code=args.exit_code,
        )
        print(action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
