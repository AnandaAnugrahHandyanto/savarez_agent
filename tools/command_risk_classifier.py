"""Deterministic shell command risk classifier for terminal preflight.

This is intentionally pattern-based and conservative. It is not a sandbox or a
complete shell parser; it is a cheap pre-exec classifier for obvious footguns
inspired by DeerFlow's SandboxAuditMiddleware. Callers can use the returned
level as report-only metadata or route WARN/BLOCK findings through the existing
approval flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import shlex
import unicodedata


class CommandRiskLevel(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class CommandRiskFinding:
    level: CommandRiskLevel
    reason: str
    pattern: str
    segment: str


@dataclass(frozen=True)
class CommandRiskResult:
    level: CommandRiskLevel
    findings: list[CommandRiskFinding]
    segments: list[str]


_RE_FLAGS = re.IGNORECASE | re.DOTALL
_COMPOUND_OPERATORS = {";", "&&", "||", "|", "&"}

# High-risk patterns should require explicit approval at minimum. Some of these
# overlap the older approval.py patterns; keeping them here makes the DeerFlow-
# style classifier independently testable and usable in report-only contexts.
_BLOCK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bcurl\b[^\n|;&]*\|\s*(?:[/\w.-]*/)?(?:ba)?sh\b", "pipe remote content to shell"),
    (r"\bwget\b[^\n|;&]*\|\s*(?:[/\w.-]*/)?(?:ba)?sh\b", "pipe remote content to shell"),
    (r"\bbase64\b[^\n|;&]*(?:-d|--decode)\b[^\n|;&]*\|\s*(?:[/\w.-]*/)?(?:ba)?sh\b", "base64 decode piped to shell"),
    (r"\b(?:cat|less|more|strings|grep|awk|sed|xargs)\b[^\n;&]*?/proc/[^\s;&|]+/environ\b", "process environment exfiltration"),
    (r"(?:^|[;&|\s])LD_PRELOAD\s*=", "LD_PRELOAD injection"),
    (r"/dev/tcp/", "raw TCP shell networking"),
    (r"\bdd\b[^\n;&]*\b(?:if|of)=/dev/(?:sd|nvme|hd|mmcblk|vd|xvd)[a-z0-9]*", "raw block device copy"),
    (r"\bmkfs(?:\.[a-z0-9]+)?\b", "format filesystem"),
    (r"\brm\s+(-[^\s]*\s+)*(?:/|/\*|~|\$HOME|/home|/root|/etc|/usr|/var|/bin|/sbin|/boot)(?:\s|/|$)", "destructive delete of protected path"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork bomb"),
    (r"\b(?:tee|cp|mv|install)\b[^\n;&]*(?:/etc/|/usr/(?:bin|sbin)/|/bin/|/sbin/|/lib/systemd/|~/.ssh/|\$HOME/.ssh/)", "write to system/startup credential path"),
)

_WARN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(?:apt|apt-get|dnf|yum|pacman|apk|brew)\b[^\n;&]*(?:install|upgrade|remove|add)\b", "package install or package-manager mutation"),
    (r"\b(?:python\s+-m\s+pip|pipx?|uv\s+pip|npm|pnpm|yarn|bun|gem|cargo)\b[^\n;&]*(?:install|add|upgrade|remove|uninstall)\b", "package install or package-manager mutation"),
    (r"(?:^|[;&|\s])PATH\s*=", "PATH mutation"),
    (r"\bchmod\b[^\n;&]*(?:\b777\b|\b666\b|a\+[rwx]*w|o\+[rwx]*w)", "world-writable permissions"),
    (r"(?:^|[;&|\s])(?:sudo|su)\b", "privilege escalation"),
)

_BLOCK_COMPILED = tuple((re.compile(pattern, _RE_FLAGS), reason, pattern) for pattern, reason in _BLOCK_PATTERNS)
_WARN_COMPILED = tuple((re.compile(pattern, _RE_FLAGS), reason, pattern) for pattern, reason in _WARN_PATTERNS)


def _normalize(command: str) -> str:
    command = command.replace("\x00", "")
    return unicodedata.normalize("NFKC", command)


def split_shell_compound(command: str) -> list[str]:
    """Split a shell command into top-level-ish segments.

    The splitter uses shlex so malformed quotes fail closed. It is deliberately
    not a full shell AST; separators inside quotes are preserved as token text,
    while common compound operators split the stream into segments for more
    precise finding locations.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    raw_tokens = list(lexer)

    segments: list[str] = []
    current: list[str] = []
    for token in raw_tokens:
        if token in _COMPOUND_OPERATORS:
            if current:
                segments.append(" ".join(current).strip())
                current = []
            continue
        # shlex may group punctuation runs such as "&&" with punctuation_chars.
        if set(token) <= set(";&|") and any(op in token for op in _COMPOUND_OPERATORS):
            if current:
                segments.append(" ".join(current).strip())
                current = []
            continue
        current.append(token)
    if current:
        segments.append(" ".join(current).strip())
    return [segment for segment in segments if segment]


def _find_matches(command: str, segments: list[str]) -> list[CommandRiskFinding]:
    findings: list[CommandRiskFinding] = []
    # Some dangerous shapes, especially pipe chains, need the full command.
    for regex, reason, pattern in _BLOCK_COMPILED:
        if regex.search(command):
            findings.append(CommandRiskFinding(CommandRiskLevel.BLOCK, reason, pattern, command))
    for regex, reason, pattern in _WARN_COMPILED:
        if regex.search(command):
            findings.append(CommandRiskFinding(CommandRiskLevel.WARN, reason, pattern, command))

    # Also classify individual compound segments so chained commands get a
    # useful localized finding instead of only a whole-command match.
    for segment in segments:
        for regex, reason, pattern in _BLOCK_COMPILED:
            if regex.search(segment) and not any(f.reason == reason and f.segment == segment for f in findings):
                findings.append(CommandRiskFinding(CommandRiskLevel.BLOCK, reason, pattern, segment))
        for regex, reason, pattern in _WARN_COMPILED:
            if regex.search(segment) and not any(f.reason == reason and f.segment == segment for f in findings):
                findings.append(CommandRiskFinding(CommandRiskLevel.WARN, reason, pattern, segment))
    return findings


def classify_terminal_command(command: str) -> CommandRiskResult:
    """Return deterministic risk classification for a shell command."""
    normalized = _normalize(command or "")
    try:
        segments = split_shell_compound(normalized)
    except ValueError as exc:
        finding = CommandRiskFinding(
            CommandRiskLevel.BLOCK,
            f"malformed shell quoting: {exc}",
            "shlex",
            normalized,
        )
        return CommandRiskResult(CommandRiskLevel.BLOCK, [finding], [])

    findings = _find_matches(normalized, segments or [normalized])
    if any(f.level is CommandRiskLevel.BLOCK for f in findings):
        level = CommandRiskLevel.BLOCK
    elif any(f.level is CommandRiskLevel.WARN for f in findings):
        level = CommandRiskLevel.WARN
    else:
        level = CommandRiskLevel.PASS
    return CommandRiskResult(level, findings, segments)
