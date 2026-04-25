"""Report-only verifier for Hermes safe orchestration routines.

This module intentionally has no runtime side effects. It evaluates a synthetic
or captured tool-call trace and returns structured findings. It never blocks,
raises for policy violations, mutates tool results, or talks to the gateway.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from typing import Any, Literal, Mapping, Sequence
import re
import shlex

FindingSeverity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class ToolCallRecord:
    """Minimal record describing one tool call for report-only evaluation."""

    name: str
    args: Mapping[str, Any]
    status: str | None = None


@dataclass(frozen=True)
class VerifierFinding:
    """One report-only verifier finding."""

    severity: FindingSeverity
    code: str
    message: str
    tool_name: str | None = None


@dataclass(frozen=True)
class VerifierReport:
    """Structured verifier result.

    ``enabled`` records that the evaluator was deliberately run. The verifier is
    still report-only: callers must not treat findings as execution blockers.
    """

    enabled: bool
    findings: tuple[VerifierFinding, ...]


_SERVICE_TARGET_RE = re.compile(r"\b(?:hermes|gateway|slack)\b", re.IGNORECASE)
_SERVICE_RESTART_RE = re.compile(
    r"\b(?:restart|reload|run\s+--replace)\b",
    re.IGNORECASE,
)
_HERMES_KILL_RE = re.compile(
    r"\b(?:kill(?:all)?|pkill)\b[^\n;|&]*(?:hermes|gateway)",
    re.IGNORECASE,
)
_SELF_UPDATE_RE = re.compile(
    r"\b(?:claude|hermes)\s+(?:update|upgrade|self-update)\b|\bself-update\b",
    re.IGNORECASE,
)
_TERMINAL_FILE_MUTATION_RE = re.compile(
    r"(?:^|[;&|\s])(?:cp|mv|tee|touch|install|chmod|chown)\b|>{1,2}",
    re.IGNORECASE,
)

_MUTATING_FILE_TOOLS = {"write_file", "patch"}
_SENSITIVE_CONFIG_NAMES = {"config.yaml", "config.yml", "credentials.json", "secrets.json"}
_SENSITIVE_CONFIG_SUFFIXES = (".pem", ".key")
_GATEWAY_ADAPTER_SEGMENTS = (
    ("gateway", "slack"),
    ("gateway", "slack_adapter.py"),
    ("slack", "adapter"),
)


def evaluate_turn(tool_calls: Sequence[ToolCallRecord]) -> VerifierReport:
    """Evaluate a turn's tool-call trace and return report-only findings.

    The function is deliberately defensive: malformed records are ignored rather
    than raised, because verifier failures must not affect live tool execution.
    """

    findings: list[VerifierFinding] = []
    for record in tool_calls:
        tool_name = _safe_str(getattr(record, "name", ""))
        args = getattr(record, "args", {})
        if not isinstance(args, Mapping):
            args = {}

        if tool_name == "terminal":
            findings.extend(_evaluate_terminal_command(args.get("command"), tool_name))
        elif tool_name in _MUTATING_FILE_TOOLS:
            findings.extend(_evaluate_mutating_path(args.get("path"), tool_name))

    return VerifierReport(enabled=True, findings=tuple(findings))


def format_report_summary(
    report: VerifierReport,
    tool_calls: Sequence[ToolCallRecord],
) -> str:
    """Return a compact, argument-free verifier summary for safe logging.

    The summary intentionally includes only counts, finding codes, statuses, and
    tool names. It never includes tool arguments, command text, paths, or file
    contents, so it is safe for logs that may be inspected during operations.
    """

    records = list(tool_calls)
    finding_counts = Counter(finding.code for finding in report.findings)
    status_counts = Counter(_safe_status(getattr(record, "status", None)) for record in records)
    tool_names = sorted({_safe_str(getattr(record, "name", "")) or "unknown" for record in records})

    parts = [
        "safe orchestration verifier summary:",
        f"tools={len(records)}",
        f"findings={len(report.findings)}",
        f"statuses={_format_counter(status_counts)}",
        f"tools_seen={','.join(tool_names) if tool_names else 'none'}",
    ]
    if finding_counts:
        parts.append(f"codes={_format_counter(finding_counts)}")
    return " ".join(parts)


def _evaluate_terminal_command(command: Any, tool_name: str) -> tuple[VerifierFinding, ...]:
    command_text = _safe_str(command)
    if not command_text:
        return ()

    findings: list[VerifierFinding] = []
    if _SERVICE_TARGET_RE.search(command_text) and _SERVICE_RESTART_RE.search(command_text):
        findings.append(_warning(
            "gateway_restart_command",
            "Terminal command appears to restart or replace a Hermes/gateway "
            "service; report-only finding.",
            tool_name,
        ))
    if _HERMES_KILL_RE.search(command_text):
        findings.append(_warning(
            "hermes_process_kill_command",
            "Terminal command appears to kill a Hermes/gateway process; report-only finding.",
            tool_name,
        ))
    if _SELF_UPDATE_RE.search(command_text):
        findings.append(_warning(
            "self_update_command",
            "Terminal command appears to run a Hermes/Claude self-update; report-only finding.",
            tool_name,
        ))
    findings.extend(_evaluate_terminal_file_targets(command_text, tool_name))
    return tuple(findings)


def _evaluate_terminal_file_targets(
    command_text: str,
    tool_name: str,
) -> tuple[VerifierFinding, ...]:
    if not _TERMINAL_FILE_MUTATION_RE.search(command_text):
        return ()

    findings: list[VerifierFinding] = []
    seen_codes: set[str] = set()
    for candidate in _extract_command_path_candidates(command_text):
        for finding in _evaluate_mutating_path(candidate, tool_name):
            if finding.code in seen_codes:
                continue
            seen_codes.add(finding.code)
            findings.append(finding)
    return tuple(findings)


def _extract_command_path_candidates(command_text: str) -> tuple[str, ...]:
    try:
        raw_tokens = shlex.split(command_text)
    except ValueError:
        raw_tokens = command_text.split()

    candidates: list[str] = []
    for token in raw_tokens:
        candidate = token.strip("'\"` ,;()[]{}")
        if not candidate or candidate.startswith("-") or candidate in {">", ">>"}:
            continue
        candidates.append(candidate)
    return tuple(candidates)


def _evaluate_mutating_path(path: Any, tool_name: str) -> tuple[VerifierFinding, ...]:
    path_text = _safe_str(path)
    if not path_text:
        return ()

    normalized = path_text.replace("\\", "/").lower()
    basename = normalized.rsplit("/", 1)[-1]
    segments = tuple(segment for segment in normalized.split("/") if segment)
    findings: list[VerifierFinding] = []

    if (
        basename in _SENSITIVE_CONFIG_NAMES
        or basename == ".env"
        or basename.startswith(".env.")
        or basename.endswith(_SENSITIVE_CONFIG_SUFFIXES)
    ):
        findings.append(_warning(
            "sensitive_config_write",
            "File mutation targets a sensitive config/env path; report-only finding.",
            tool_name,
        ))

    if _has_ordered_segments(segments, _GATEWAY_ADAPTER_SEGMENTS):
        findings.append(_warning(
            "gateway_adapter_write",
            "File mutation targets gateway/Slack adapter code; report-only finding.",
            tool_name,
        ))

    return tuple(findings)


def _has_ordered_segments(
    path_segments: tuple[str, ...],
    segment_patterns: tuple[tuple[str, ...], ...],
) -> bool:
    for pattern in segment_patterns:
        max_start = len(path_segments) - len(pattern) + 1
        if max_start <= 0:
            continue
        if any(path_segments[index:index + len(pattern)] == pattern for index in range(max_start)):
            return True
    return False


def _warning(code: str, message: str, tool_name: str) -> VerifierFinding:
    return VerifierFinding(
        severity="warning",
        code=code,
        message=message,
        tool_name=tool_name,
    )


def _safe_status(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return "unknown"


def _format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "none"
    return ",".join(f"{key}:{counter[key]}" for key in sorted(counter))


def _safe_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""
