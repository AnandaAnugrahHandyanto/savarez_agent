"""Observe-only instruction-surface manifest helpers.

This module records where system-prompt instruction blocks came from without
changing the rendered prompt text. It is deliberately pure and deterministic:
hashes live in manifests/logs, never in the normal prompt.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal

logger = logging.getLogger(__name__)

InstructionTier = Literal["stable", "context", "volatile", "ephemeral"]
TrustLevel = Literal["trusted", "workspace", "untrusted", "derived"]
CachePolicy = Literal["stable", "session", "turn", "tool_result"]


@dataclass(frozen=True)
class InstructionBlock:
    id: str
    surface: str
    tier: InstructionTier
    authority: int
    scope: str
    path: str | None
    origin: str
    content: str
    trust: TrustLevel
    cache_policy: CachePolicy
    labels: frozenset[str] = field(default_factory=frozenset)
    can_override: frozenset[str] = field(default_factory=frozenset)
    truncated: bool = False
    threat_status: str = "unknown"

    @property
    def hash(self) -> str:
        return "sha256:" + hashlib.sha256(_normalize(self.content).encode("utf-8")).hexdigest()

    def summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "surface": self.surface,
            "tier": self.tier,
            "authority": self.authority,
            "scope": self.scope,
            "path": self.path,
            "origin": self.origin,
            "hash": self.hash,
            "chars": len(self.content),
            "truncated": self.truncated,
            "threat_status": self.threat_status,
            "trust": self.trust,
            "cache_policy": self.cache_policy,
            "labels": sorted(self.labels),
        }


@dataclass(frozen=True)
class InstructionConflict:
    severity: Literal["hard", "soft"]
    conflict_class: str
    winner: str
    loser: str
    reason: str
    action: Literal["observe", "warn", "block"] = "observe"

    def summary(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "class": self.conflict_class,
            "winner": self.winner,
            "loser": self.loser,
            "reason": self.reason,
            "action": self.action,
        }


@dataclass
class ResolvedInstructionSurface:
    stable: str
    context: str
    volatile: str
    ephemeral: str | None
    manifest: list[dict[str, object]]
    conflicts: list[dict[str, str]]
    blocked: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _normalize(content: str) -> str:
    return content.replace("\r\n", "\n").replace("\r", "\n")


def make_instruction_block(
    *,
    id: str,
    content: str,
    surface: str,
    tier: InstructionTier,
    authority: int,
    scope: str,
    origin: str,
    path: str | None = None,
    trust: TrustLevel = "trusted",
    cache_policy: CachePolicy = "session",
    labels: Iterable[str] = (),
    can_override: Iterable[str] = (),
    threat_status: str | None = None,
) -> InstructionBlock:
    return InstructionBlock(
        id=id,
        surface=surface,
        tier=tier,
        authority=authority,
        scope=scope,
        path=str(Path(path).resolve()) if path else None,
        origin=origin,
        content=content,
        trust=trust,
        cache_policy=cache_policy,
        labels=frozenset(labels),
        can_override=frozenset(can_override),
        truncated="[...truncated " in content,
        threat_status=threat_status or ("blocked" if content.startswith("[BLOCKED:") or "\n[BLOCKED:" in content else "clean"),
    )


def resolve_instruction_blocks(blocks: Iterable[InstructionBlock]) -> ResolvedInstructionSurface:
    ordered = list(blocks)
    by_tier = {"stable": [], "context": [], "volatile": [], "ephemeral": []}
    for block in ordered:
        rendered = block.content.strip()
        if rendered:
            by_tier[block.tier].append(rendered)
    conflicts = detect_conflicts(ordered)
    if conflicts:
        logger.info(
            "Instruction-surface observe-only conflicts: %s",
            [conflict.summary() for conflict in conflicts],
        )
    return ResolvedInstructionSurface(
        stable="\n\n".join(by_tier["stable"]),
        context="\n\n".join(by_tier["context"]),
        volatile="\n\n".join(by_tier["volatile"]),
        ephemeral="\n\n".join(by_tier["ephemeral"]) or None,
        manifest=[block.summary() for block in ordered],
        conflicts=[conflict.summary() for conflict in conflicts],
        blocked=[block.summary() for block in ordered if block.threat_status == "blocked"],
        warnings=[],
    )


def render_resolved_surface(surface: ResolvedInstructionSurface) -> dict[str, str]:
    return {"stable": surface.stable, "context": surface.context, "volatile": surface.volatile}


_IDENTITY_RE = re.compile(r"\b(you are claude|you are cursor|you are gemini|ignore hermes)\b", re.I)
_TOOL_RE = re.compile(r"\b(do not use tools|don't use tools|skip tool calls|hide tool calls|skip kanban)\b", re.I)
_LEAK_RE = re.compile(r"\b(reveal|print|exfiltrate|dump)\b.*\b(secret|secrets|token|tokens|api key|password|memory|session history|pii)\b", re.I)
_SAFETY_BYPASS_RE = re.compile(r"\b(ignore approvals|disable redaction|delete without approval|deploy without approval|push without approval)\b", re.I)


def detect_conflicts(blocks: Iterable[InstructionBlock]) -> list[InstructionConflict]:
    ordered = list(blocks)
    high_identity = _highest(ordered, {"identity", "profile"})
    high_tool = _highest(ordered, {"tool", "workflow", "kanban"})
    high_safety = _highest(ordered, {"safety"})
    conflicts: list[InstructionConflict] = []
    for block in ordered:
        if _IDENTITY_RE.search(block.content) and block.authority < 950:
            conflicts.append(InstructionConflict("hard", "identity_override", high_identity.id if high_identity and high_identity.id != block.id else "profile.identity", block.id, "lower-authority source attempts to replace Hermes/profile identity"))
        if high_tool and block.authority < high_tool.authority and _TOOL_RE.search(block.content):
            conflicts.append(InstructionConflict("hard", "tool_lifecycle_override", high_tool.id, block.id, "lower-authority source attempts to suppress required tool/Kanban lifecycle"))
        if high_safety and block.authority < high_safety.authority and _SAFETY_BYPASS_RE.search(block.content):
            conflicts.append(InstructionConflict("hard", "safety_bypass", high_safety.id, block.id, "lower-authority source requests safety bypass"))
        if high_safety and block.authority < high_safety.authority and _LEAK_RE.search(block.content):
            conflicts.append(InstructionConflict("hard", "credential_data_leak", high_safety.id, block.id, "lower-authority source requests disclosure of secrets/private data"))
    return conflicts


def _highest(blocks: Iterable[InstructionBlock], labels: set[str]) -> InstructionBlock | None:
    candidates = [block for block in blocks if block.labels & labels]
    return max(candidates, key=lambda block: block.authority, default=None)


def build_project_context_manifest(cwd: str | Path) -> InstructionBlock | None:
    """Return the winning current project-context source as a manifest block.

    Mirrors build_context_files_prompt precedence without adding GEMINI.md yet.
    GEMINI.md is intentionally deferred to Phase C; tests document this TODO.
    """
    from agent.prompt_builder import _find_hermes_md

    cwd_path = Path(cwd).resolve()
    hermes_md = _find_hermes_md(cwd_path)
    if hermes_md and hermes_md.is_file():
        return _file_block("project.HERMES_MD", hermes_md, 650, ".hermes.md / HERMES.md")
    for name in ("AGENTS.md", "agents.md"):
        candidate = cwd_path / name
        if candidate.is_file():
            return _file_block("project.AGENTS", candidate, 600, "AGENTS.md / agents.md")
    for name in ("CLAUDE.md", "claude.md"):
        candidate = cwd_path / name
        if candidate.is_file():
            return _file_block("project.CLAUDE", candidate, 560, "CLAUDE.md / claude.md")
    if (cwd_path / ".cursorrules").is_file() or (cwd_path / ".cursor" / "rules").is_dir():
        path = cwd_path / ".cursorrules" if (cwd_path / ".cursorrules").is_file() else cwd_path / ".cursor" / "rules"
        return _file_block("project.CURSOR", path, 560, ".cursorrules / .cursor/rules/*.mdc")
    return None


def _file_block(block_id: str, path: Path, authority: int, origin: str) -> InstructionBlock:
    content = ""
    if path.is_file():
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            content = ""
    return make_instruction_block(
        id=block_id,
        surface="project",
        tier="context",
        authority=authority,
        scope="project",
        path=str(path),
        origin=origin,
        content=content,
        trust="workspace",
        cache_policy="session",
        labels={"project", "workflow"},
    )
