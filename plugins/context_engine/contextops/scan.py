"""``contextops scan`` CLI vertical slice.

Loads an exported JSON snapshot of Hermes-like dogfood evidence, runs the
read-only exporter/detectors in :mod:`plugins.context_engine.contextops.dogfood`,
and emits a deterministic operator-facing report. The CLI is strictly
suggestion-only: it never mutates Hermes state, never sends, never dispatches,
and never echoes raw ids, channels, transcripts, paths, or secrets into its
output (all such fields are reduced to opaque ``ref:<hex>`` digests by the
underlying adapter).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from contextops_ese import SCHEMA_VERSION, SafetyDecision, assert_text_safe, scan_unsafe

from .dogfood import (
    _assert_no_output_leaks,
    detect_dogfood_findings,
    export_hermes_dogfood_observations,
)

SCAN_SCHEMA_VERSION = "contextops.scan_report.v0"

_SCAN_SAFETY = SafetyDecision(
    status="allow_suggestion",
    policy_mode="suggestion_only",
    read_only=True,
    mutation_allowed=False,
    dispatch_allowed=False,
    reason="contextops scan is read-only; operator owns any follow-up action",
)


def run_scan(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Run the read-only exporter + detectors and assemble a scan report.

    The returned dict is deterministic for a given snapshot, carries the
    versioned scan-report envelope, and only contains opaque provenance refs.
    """

    if not isinstance(snapshot, dict):
        raise TypeError("scan snapshot must be a mapping")

    observations = export_hermes_dogfood_observations(snapshot)
    findings = detect_dogfood_findings(observations)
    # Sort findings deterministically by kind then by finding_ref so the
    # operator-facing report does not jitter between runs.
    findings_sorted = sorted(findings, key=lambda f: (f.get("kind", ""), f.get("finding_ref", "")))

    counts = {
        "runtime_events": len(observations.get("runtime_events", [])),
        "messages": len(observations.get("messages", [])),
        "tasks": len(observations.get("tasks", [])),
    }

    report: dict[str, Any] = {
        "schema_version": SCAN_SCHEMA_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "finding_count": len(findings_sorted),
        "observation_counts": counts,
        "findings": findings_sorted,
        "safety_decision": _SCAN_SAFETY.to_dict(),
    }
    _assert_no_output_leaks(report)
    return report


def render_scan_report(report: dict[str, Any]) -> str:
    """Render a scan report as concise leak-safe operator-facing text."""

    safety = report.get("safety_decision", {})
    counts = report.get("observation_counts", {})
    lines = [
        "ContextOps scan report",
        f"schema_version: {report.get('schema_version', SCAN_SCHEMA_VERSION)}",
        (
            f"observations: runtime_events={counts.get('runtime_events', 0)}, "
            f"messages={counts.get('messages', 0)}, tasks={counts.get('tasks', 0)}"
        ),
        f"policy: {safety.get('policy_mode', 'suggestion_only')}",
        (
            f"safety: read_only={'true' if safety.get('read_only') else 'false'}, "
            f"mutation_allowed={'true' if safety.get('mutation_allowed') else 'false'}, "
            f"dispatch_allowed={'true' if safety.get('dispatch_allowed') else 'false'}"
        ),
        f"findings ({report.get('finding_count', 0)}):",
    ]
    for finding in report.get("findings", []):
        kind = finding.get("kind", "unknown")
        confidence = float(finding.get("confidence", 0.0) or 0.0)
        finding_ref = finding.get("finding_ref", "")
        action = finding.get("recommendation", {}).get("suggested_operator_action", "")
        evidence_refs = finding.get("evidence", {}).get("evidence_refs", []) or []
        lines.append(f"  - {kind} [{finding_ref}] confidence={confidence:.2f}")
        lines.append(f"      action: {action}")
        if evidence_refs:
            lines.append(f"      evidence: {' '.join(evidence_refs)}")
    text = "\n".join(lines)
    _assert_rendered_text_safe(text)
    return text


def _assert_rendered_text_safe(text: str) -> None:
    """Final adapter-side leak gate over the rendered report text.

    Splits each line on whitespace, strips opaque ``ref:`` tokens, and runs the
    remaining text through the core leak scanner. Fails closed on any hit.
    """

    for line in text.splitlines():
        scrubbed_tokens = [tok for tok in line.split() if not tok.startswith("ref:")]
        scrubbed = " ".join(scrubbed_tokens)
        if not scrubbed:
            continue
        reason = scan_unsafe(scrubbed)
        if reason is not None:
            raise ValueError(f"scan text rejected by leak gate: {reason}")


def _load_snapshot(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("snapshot JSON must decode to an object")
    return data


def scan_cli(argv: list[str] | None = None) -> str:
    """Run the ``contextops scan`` CLI and return its rendered output.

    ``--format text`` (default) emits the operator-facing summary; ``json``
    emits the full report so it can be piped into downstream tooling.
    """

    parser = argparse.ArgumentParser(
        prog="contextops scan",
        description=(
            "Read-only ContextOps scan over an exported evidence snapshot. "
            "Emits suggestion-only findings with opaque provenance refs; never "
            "mutates Hermes state, never dispatches, never sends."
        ),
    )
    parser.add_argument(
        "--snapshot",
        required=True,
        help="path to a JSON snapshot exported from the read-only dogfood adapter",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        default=True,
        help="always on; the scan never mutates (kept for CLI parity)",
    )
    args = parser.parse_args(argv)

    snapshot_path = Path(args.snapshot).expanduser()
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"snapshot path is not a readable file")

    snapshot = _load_snapshot(snapshot_path)
    report = run_scan(snapshot)
    if args.format == "json":
        return json.dumps(report, sort_keys=True, indent=2)
    # Validate the static prelude once before assembling the full text so a
    # regression in the renderer cannot bypass the rendered-text gate.
    assert_text_safe("ContextOps scan report", "scan title")
    return render_scan_report(report)


def main(argv: list[str] | None = None) -> None:
    """Console entrypoint for ``contextops scan``.

    The installed script accepts the product command shape
    ``contextops scan --snapshot ...``. For local smoke tests, invoking the
    entrypoint without the subcommand still delegates to ``scan_cli`` so the
    implementation remains one vertical slice.
    """

    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "scan":
        args = args[1:]
    elif args and args[0] in {"-h", "--help"}:
        print("usage: contextops scan --snapshot SNAPSHOT [--format {text,json}]")
        return
    output = scan_cli(args)
    print(output)


if __name__ == "__main__":  # pragma: no cover - exercised by console script
    main()
